import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../services/api';
import { useWebSocket } from './WebSocketContext';
import { useAuth } from './AuthContext';

const CallContext = createContext(null);

export function CallProvider({ children }) {
  const { user } = useAuth();
  const { ws, subscribe } = useWebSocket() || {};

  const [activeCall, setActiveCall] = useState(null);
  const [incomingCall, setIncomingCall] = useState(null);
  const [callStatus, setCallStatus] = useState('idle');
  const [localStream, setLocalStream] = useState(null);
  const [remoteStream, setRemoteStream] = useState(null);
  const [callDuration, setCallDuration] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);
  
  const localVideoRef = useRef(null);
  const remoteVideoRef = useRef(null);
  const streamRef = useRef(null);
  const peerConnectionRef = useRef(null);
  const ringTimeoutRef = useRef(null);
  const statusRef = useRef('idle');
  const wsRef = useRef(null);
  const activeCallRef = useRef(null);

  // Queue for signals that arrive before the PeerConnection is ready
  const pendingSignalsRef = useRef([]);
  // Flag to prevent creating PC multiple times
  const pcCreatedForCallRef = useRef(null);

  // Ringtone synthesizer state
  const ringtoneOscRef = useRef(null);
  const ringtoneCtxRef = useRef(null);

  // Keep refs in sync with state
  useEffect(() => {
    statusRef.current = callStatus;
  }, [callStatus]);

  useEffect(() => {
    wsRef.current = ws;
  }, [ws]);

  useEffect(() => {
    activeCallRef.current = activeCall;
  }, [activeCall]);

  const startRingtone = () => {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      ringtoneCtxRef.current = ctx;

      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gainNode = ctx.createGain();

      osc1.frequency.value = 440;
      osc2.frequency.value = 480;

      osc1.connect(gainNode);
      osc2.connect(gainNode);
      gainNode.connect(ctx.destination);

      gainNode.gain.setValueAtTime(0, ctx.currentTime);

      const playRing = (time) => {
        gainNode.gain.setValueAtTime(0.08, time);
        gainNode.gain.exponentialRampToValueAtTime(0.08, time + 0.1);
        gainNode.gain.setValueAtTime(0.08, time + 2.0);
        gainNode.gain.exponentialRampToValueAtTime(0.0001, time + 2.2);
      };

      osc1.start();
      osc2.start();

      let startTime = ctx.currentTime;
      for (let i = 0; i < 15; i++) {
        playRing(startTime + i * 4); // Rings every 4 seconds
      }

      ringtoneOscRef.current = [osc1, osc2, gainNode];
    } catch (e) {
      console.error("Failed to play synthesized ringtone:", e);
    }
  };

  const stopRingtone = () => {
    if (ringtoneOscRef.current) {
      ringtoneOscRef.current.forEach(node => {
        try {
          node.stop();
        } catch (e) {}
        try {
          node.disconnect();
        } catch (e) {}
      });
      ringtoneOscRef.current = null;
    }
    if (ringtoneCtxRef.current) {
      try {
        ringtoneCtxRef.current.close();
      } catch (e) {}
      ringtoneCtxRef.current = null;
    }
  };

  const acquireMediaStream = async () => {
    // If we already have a stream, reuse it
    if (streamRef.current && streamRef.current.active) {
      return streamRef.current;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      setLocalStream(stream);
      streamRef.current = stream;
      return stream;
    } catch (err) {
      console.error("Failed to access camera/microphone:", err);
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        setLocalStream(stream);
        streamRef.current = stream;
        return stream;
      } catch (e) {
        console.error("Failed to access camera even without audio:", e);
        return null;
      }
    }
  };

  const stopLocalCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setLocalStream(null);
    setIsMuted(false);
    setIsVideoOff(false);
  };

  const toggleMute = () => {
    const stream = streamRef.current || localStream;
    if (stream) {
      stream.getAudioTracks().forEach(track => {
        track.enabled = !track.enabled;
        setIsMuted(!track.enabled);
      });
    }
  };

  const toggleVideo = () => {
    const stream = streamRef.current || localStream;
    if (stream) {
      stream.getVideoTracks().forEach(track => {
        track.enabled = !track.enabled;
        setIsVideoOff(!track.enabled);
      });
    }
  };

  // --- Core WebRTC helpers ---

  const closePeerConnection = () => {
    if (peerConnectionRef.current) {
      try {
        peerConnectionRef.current.close();
      } catch (e) {
        console.error("[WebRTC] Error closing peer connection:", e);
      }
      peerConnectionRef.current = null;
    }
    pcCreatedForCallRef.current = null;
    pendingSignalsRef.current = [];
    setRemoteStream(null);
  };

  const createPeerConnection = (peerId, role) => {
    // Prevent double-creation for the same call
    if (peerConnectionRef.current && pcCreatedForCallRef.current === peerId) {
      console.log("[WebRTC] PeerConnection already exists for peer:", peerId);
      return peerConnectionRef.current;
    }

    // Close any leftover PC
    if (peerConnectionRef.current) {
      try { peerConnectionRef.current.close(); } catch (e) {}
      peerConnectionRef.current = null;
    }

    console.log("[WebRTC] Creating RTCPeerConnection for peer:", peerId, "role:", role);
    const pc = new RTCPeerConnection({
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' },
        { urls: 'stun:stun2.l.google.com:19302' },
        { urls: 'stun:stun3.l.google.com:19302' },
        { urls: 'stun:stun4.l.google.com:19302' }
      ]
    });
    peerConnectionRef.current = pc;
    pcCreatedForCallRef.current = peerId;

    pc.onicecandidate = (event) => {
      if (event.candidate && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        console.log("[WebRTC] Sending ICE candidate to peer:", peerId);
        wsRef.current.send(JSON.stringify({
          event: 'signal',
          to_user_id: peerId,
          data: { ice: event.candidate }
        }));
      }
    };

    pc.ontrack = (event) => {
      console.log("[WebRTC] Received remote track:", event.track.kind);
      if (event.streams && event.streams[0]) {
        setRemoteStream(event.streams[0]);
      }
    };

    pc.oniceconnectionstatechange = () => {
      console.log("[WebRTC] ICE state:", pc.iceConnectionState);
      if (pc.iceConnectionState === 'failed') {
        console.warn("[WebRTC] ICE connection failed, attempting restart...");
        try { pc.restartIce(); } catch (e) {}
      }
      if (pc.iceConnectionState === 'disconnected' || pc.iceConnectionState === 'closed') {
        console.log("[WebRTC] Peer disconnected/closed");
      }
    };

    pc.onconnectionstatechange = () => {
      console.log("[WebRTC] Connection state:", pc.connectionState);
    };

    return pc;
  };

  const addLocalTracksToPC = (pc, stream) => {
    if (!pc || !stream) return;
    // Check if tracks are already added
    const senders = pc.getSenders();
    const existingTrackIds = senders.map(s => s.track?.id).filter(Boolean);
    
    stream.getTracks().forEach(track => {
      if (!existingTrackIds.includes(track.id)) {
        console.log("[WebRTC] Adding local track:", track.kind, track.id);
        pc.addTrack(track, stream);
      }
    });
  };

  const createAndSendOffer = async (pc, peerId) => {
    try {
      console.log("[WebRTC] Creating SDP offer...");
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      console.log("[WebRTC] Sending offer to peer:", peerId);
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          event: 'signal',
          to_user_id: peerId,
          data: { sdp: pc.localDescription }
        }));
      }
    } catch (err) {
      console.error("[WebRTC] Failed to create/send offer:", err);
    }
  };

  const processPendingSignals = async (pc) => {
    const signals = [...pendingSignalsRef.current];
    pendingSignalsRef.current = [];
    for (const { fromUserId, data } of signals) {
      console.log("[WebRTC] Processing queued signal from:", fromUserId);
      await processSignal(pc, fromUserId, data);
    }
  };

  const processSignal = async (pc, fromUserId, data) => {
    if (!pc) {
      console.warn("[WebRTC] No PeerConnection, queuing signal from:", fromUserId);
      pendingSignalsRef.current.push({ fromUserId, data });
      return;
    }

    if (data.sdp) {
      const sdp = new RTCSessionDescription(data.sdp);
      console.log(`[WebRTC] Received ${sdp.type} from:`, fromUserId);
      try {
        await pc.setRemoteDescription(sdp);
        
        // Drain any queued ICE candidates for this peer now that remote description is set
        const remainingSignals = [];
        for (const sig of pendingSignalsRef.current) {
          if (sig.fromUserId === fromUserId && sig.data.ice) {
            console.log("[WebRTC] Draining queued ICE candidate after remote description set");
            try {
              await pc.addIceCandidate(new RTCIceCandidate(sig.data.ice));
            } catch (e) {
              console.error("[WebRTC] Error adding drained ICE candidate:", e);
            }
          } else {
            remainingSignals.push(sig);
          }
        }
        pendingSignalsRef.current = remainingSignals;

        if (sdp.type === 'offer') {
          console.log("[WebRTC] Creating SDP answer...");
          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          console.log("[WebRTC] Sending answer to:", fromUserId);
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
              event: 'signal',
              to_user_id: fromUserId,
              data: { sdp: pc.localDescription }
            }));
          }
        }
      } catch (err) {
        console.error("[WebRTC] Error handling SDP:", err);
      }
    } else if (data.ice) {
      console.log("[WebRTC] Received ICE candidate from:", fromUserId);
      try {
        // If remote description not yet set, queue the candidate
        if (!pc.remoteDescription) {
          console.log("[WebRTC] Remote description not set yet, queuing ICE candidate");
          pendingSignalsRef.current.push({ fromUserId, data });
          return;
        }
        await pc.addIceCandidate(new RTCIceCandidate(data.ice));
      } catch (err) {
        console.error("[WebRTC] Error adding ICE candidate:", err);
      }
    }
  };

  // --- Setup WebRTC connection (called when both status=connected AND we have call info) ---
  const setupWebRTCConnection = async (callInfo) => {
    const { peer_id, role } = callInfo;
    
    console.log("[WebRTC] Setting up connection. Role:", role, "Peer:", peer_id);

    // 1. Create peer connection
    const pc = createPeerConnection(peer_id, role);

    // 2. Acquire media stream
    const stream = await acquireMediaStream();
    if (!stream) {
      console.error("[WebRTC] Could not acquire media stream!");
      return;
    }

    // 3. Add local tracks to PC
    addLocalTracksToPC(pc, stream);

    // 4. Process any queued signals (offers/ICE from the other side)
    await processPendingSignals(pc);

    // 5. If doctor role, create and send the SDP offer
    if (role === 'doctor') {
      // Small delay to let the patient side initialize
      await new Promise(r => setTimeout(r, 500));
      await createAndSendOffer(pc, peer_id);
    }
  };

  // --- Call Action Handlers ---

  const handleStartCall = async (chatId, otherPartyName, appointmentId = null) => {
    try {
      setCallStatus('ringing');
      setActiveCall({
        role: 'doctor',
        otherPartyName: otherPartyName
      });
      
      const res = await api.initiateCall(appointmentId || null, chatId || null);
      setActiveCall(prev => ({
        ...prev,
        call_id: res.call_id,
        room_id: res.room_id,
        peer_id: res.peer_id
      }));
      
      // Pre-acquire media stream while waiting for patient to accept
      acquireMediaStream();
    } catch (err) {
      console.error(err);
      alert("Failed to start video call: " + err.message);
      setCallStatus('idle');
      setActiveCall(null);
    }
  };

  const handleAcceptCall = async () => {
    if (!incomingCall) return;
    try {
      // Stop ringtone immediately
      stopRingtone();
      
      const res = await api.acceptCall(incomingCall.call_id);
      
      const callInfo = {
        call_id: incomingCall.call_id,
        room_id: incomingCall.room_id,
        peer_id: res.peer_id,
        role: 'patient',
        otherPartyName: incomingCall.doctor_name
      };
      
      setActiveCall(callInfo);
      setIncomingCall(null);
      setCallStatus('connected');
      
      // Setup WebRTC after state is set
      // Use setTimeout to ensure state updates are processed first
      setTimeout(() => {
        setupWebRTCConnection(callInfo);
      }, 100);
    } catch (err) {
      console.error(err);
      alert("Failed to accept call: " + err.message);
      setIncomingCall(null);
      setCallStatus('idle');
    }
  };

  const handleRejectCall = async () => {
    if (!incomingCall) return;
    try {
      await api.rejectCall(incomingCall.call_id);
    } catch (err) {
      console.error(err);
    } finally {
      stopRingtone();
      setIncomingCall(null);
      setCallStatus('idle');
    }
  };

  const handleEndCall = async () => {
    const callId = activeCall?.call_id || incomingCall?.call_id;
    
    closePeerConnection();
    stopRingtone();

    if (!callId) {
      stopLocalCamera();
      setActiveCall(null);
      setIncomingCall(null);
      setCallStatus('idle');
      return;
    }
    
    try {
      await api.endCall(callId);
    } catch (err) {
      console.error(err);
    } finally {
      stopLocalCamera();
      setActiveCall(null);
      setIncomingCall(null);
      setCallStatus('idle');
    }
  };

  // --- Video element srcObject binding with retry ---
  // Deleted: we now use callback refs in Layout.jsx to avoid React render race conditions.

  // Duration effect
  useEffect(() => {
    let interval = null;
    if (callStatus === 'connected') {
      interval = setInterval(() => {
        setCallDuration(prev => prev + 1);
      }, 1000);
    } else {
      setCallDuration(0);
    }
    return () => clearInterval(interval);
  }, [callStatus]);

  // Outbound ringing timeout
  useEffect(() => {
    if (callStatus === 'ringing' && activeCall && activeCall.role === 'doctor') {
      if (ringTimeoutRef.current) {
        clearTimeout(ringTimeoutRef.current);
      }
      ringTimeoutRef.current = setTimeout(() => {
        if (statusRef.current === 'ringing') {
          console.log("Ringing timed out. Ending call as MISSED.");
          handleEndCall();
        }
      }, 30000); // 30 seconds
    } else {
      if (ringTimeoutRef.current) {
        clearTimeout(ringTimeoutRef.current);
        ringTimeoutRef.current = null;
      }
    }
    return () => {
      if (ringTimeoutRef.current) {
        clearTimeout(ringTimeoutRef.current);
      }
    };
  }, [callStatus, activeCall]);

  // Ringtone playback hook
  useEffect(() => {
    if (callStatus === 'ringing' && incomingCall) {
      startRingtone();
    } else {
      stopRingtone();
    }
    return () => {
      stopRingtone();
    };
  }, [callStatus, incomingCall]);

  // Speech and metadata state changes
  useEffect(() => {
    const inCall = callStatus !== 'idle';
    localStorage.setItem('is_in_call', inCall ? 'true' : 'false');
    window.dispatchEvent(new Event('call_state_change'));
    
    if (inCall) {
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    }
  }, [callStatus]);

  // Cleanup PC when call ends
  useEffect(() => {
    if (callStatus === 'idle') {
      closePeerConnection();
    }
  }, [callStatus]);

  // Subscribe to WS signaling events globally
  useEffect(() => {
    if (!subscribe || !user) return;
    
    const unsubscribe = subscribe((data) => {
      if (data.event === 'call_initiated') {
        // Patient receives incoming call
        setIncomingCall({
          call_id: data.data.call_id,
          room_id: data.data.room_id,
          doctor_name: data.data.doctor_name,
          peer_id: data.data.peer_id
        });
        setCallStatus('ringing');
      } else if (data.event === 'accepted') {
        // Doctor receives acceptance from patient
        console.log("[Call] Patient accepted. Setting up WebRTC as doctor...");
        
        const currentCall = activeCallRef.current;
        const updatedCall = currentCall ? {
          ...currentCall,
          peer_id: data.data.peer_id
        } : null;
        
        setActiveCall(updatedCall);
        setCallStatus('connected');
        
        // Setup WebRTC connection as doctor
        if (updatedCall) {
          setTimeout(() => {
            setupWebRTCConnection(updatedCall);
          }, 100);
        }
      } else if (data.event === 'rejected') {
        setCallStatus('declined');
        stopLocalCamera();
        closePeerConnection();
        setTimeout(() => {
          setActiveCall(null);
          setCallStatus('idle');
        }, 2500);
      } else if (data.event === 'left') {
        setCallStatus('ended');
        closePeerConnection();
        stopLocalCamera();
        setTimeout(() => {
          setActiveCall(null);
          setIncomingCall(null);
          setCallStatus('idle');
        }, 2000);
      } else if (data.event === 'signal') {
        // WebRTC signaling: SDP or ICE candidate
        const pc = peerConnectionRef.current;
        if (pc) {
          processSignal(pc, data.from_user_id, data.data);
        } else {
          // Queue the signal - the PC isn't ready yet
          console.log("[WebRTC] PC not ready, queuing signal from:", data.from_user_id);
          pendingSignalsRef.current.push({ fromUserId: data.from_user_id, data: data.data });
        }
      }
    });
    
    return unsubscribe;
  }, [subscribe, user]);

  // Check for active call on login
  useEffect(() => {
    if (!user) {
      stopLocalCamera();
      closePeerConnection();
      setActiveCall(null);
      setIncomingCall(null);
      setCallStatus('idle');
      return;
    }

    const checkActiveCall = async () => {
      try {
        const data = await api.getActiveCall();
        if (data && data.has_active_call) {
          if (data.role === 'patient') {
            if (data.status === 'INITIATED' || data.status === 'RINGING') {
              setIncomingCall({
                call_id: data.call_id,
                room_id: data.room_id,
                doctor_name: data.other_party_name,
                peer_id: data.peer_id
              });
              setCallStatus('ringing');
            } else if (data.status === 'ACCEPTED' || data.status === 'ONGOING') {
              const callInfo = {
                call_id: data.call_id,
                room_id: data.room_id,
                peer_id: data.peer_id,
                role: 'patient',
                otherPartyName: data.other_party_name
              };
              setActiveCall(callInfo);
              setCallStatus('connected');
              setTimeout(() => setupWebRTCConnection(callInfo), 500);
            }
          } else if (data.role === 'doctor') {
            const callInfo = {
              call_id: data.call_id,
              room_id: data.room_id,
              peer_id: data.peer_id,
              role: 'doctor',
              otherPartyName: data.other_party_name
            };
            setActiveCall(callInfo);
            if (data.status === 'INITIATED' || data.status === 'RINGING') {
              setCallStatus('ringing');
            } else {
              setCallStatus('connected');
              setTimeout(() => setupWebRTCConnection(callInfo), 500);
            }
          }
        }
      } catch (err) {
        console.error("Failed to fetch active call on load:", err);
      }
    };

    checkActiveCall();
  }, [user]);

  return (
    <CallContext.Provider value={{
      activeCall,
      incomingCall,
      callStatus,
      localStream,
      remoteStream,
      callDuration,
      isMuted,
      isVideoOff,
      localVideoRef,
      remoteVideoRef,
      handleStartCall,
      handleAcceptCall,
      handleRejectCall,
      handleEndCall,
      toggleMute,
      toggleVideo
    }}>
      {children}
    </CallContext.Provider>
  );
}

export const useCall = () => useContext(CallContext);
