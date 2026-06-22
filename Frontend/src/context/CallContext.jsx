import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
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

  // Ringtone synthesizer state
  const ringtoneOscRef = useRef(null);
  const ringtoneCtxRef = useRef(null);

  useEffect(() => {
    statusRef.current = callStatus;
  }, [callStatus]);

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

  const startLocalCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      setLocalStream(stream);
      streamRef.current = stream;
    } catch (err) {
      console.error("Failed to access camera/microphone:", err);
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        setLocalStream(stream);
        streamRef.current = stream;
      } catch (e) {
        console.error("Failed to access camera even without audio:", e);
      }
    }
  };

  const stopLocalCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (localStream) {
      localStream.getTracks().forEach(track => track.stop());
      setLocalStream(null);
    }
  };

  const toggleMute = () => {
    if (streamRef.current) {
      const audioTrack = streamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        setIsMuted(!audioTrack.enabled);
      }
    }
  };

  const toggleVideo = () => {
    if (streamRef.current) {
      const videoTrack = streamRef.current.getVideoTracks()[0];
      if (videoTrack) {
        videoTrack.enabled = !videoTrack.enabled;
        setIsVideoOff(!videoTrack.enabled);
      }
    }
  };

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
      
      startLocalCamera();
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
      const res = await api.acceptCall(incomingCall.call_id);
      setActiveCall({
        call_id: incomingCall.call_id,
        room_id: incomingCall.room_id,
        peer_id: res.peer_id,
        role: 'patient',
        otherPartyName: incomingCall.doctor_name
      });
      setIncomingCall(null);
      setCallStatus('connected');
      
      startLocalCamera();
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
      setIncomingCall(null);
      setCallStatus('idle');
    }
  };

  const handleEndCall = async () => {
    const callId = activeCall?.call_id || incomingCall?.call_id;
    
    if (peerConnectionRef.current) {
      try {
        peerConnectionRef.current.close();
      } catch (e) {
        console.error("Error closing WebRTC peer connection:", e);
      }
      peerConnectionRef.current = null;
    }
    
    setRemoteStream(null);
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

  // Video attachments effects
  useEffect(() => {
    if (localStream && localVideoRef.current) {
      localVideoRef.current.srcObject = localStream;
    }
  }, [localStream, callStatus, activeCall]);

  useEffect(() => {
    if (remoteStream && remoteVideoRef.current) {
      remoteVideoRef.current.srcObject = remoteStream;
    }
  }, [remoteStream, callStatus, activeCall]);

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

  // WebRTC Peer Connection & Negotiation Effect
  useEffect(() => {
    if (callStatus !== 'connected' || !activeCall || !activeCall.peer_id) {
      if (peerConnectionRef.current) {
        console.log("[WebRTC] Closing RTCPeerConnection on status change");
        peerConnectionRef.current.close();
        peerConnectionRef.current = null;
      }
      setRemoteStream(null);
      return;
    }

    console.log("[WebRTC] Setting up RTCPeerConnection for peer:", activeCall.peer_id);
    const pc = new RTCPeerConnection({
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' },
        { urls: 'stun:stun2.l.google.com:19302' }
      ]
    });
    peerConnectionRef.current = pc;

    pc.onicecandidate = (event) => {
      if (event.candidate && ws && ws.readyState === WebSocket.OPEN) {
        console.log("[WebRTC] Sending local ICE candidate to:", activeCall.peer_id);
        ws.send(JSON.stringify({
          event: 'signal',
          to_user_id: activeCall.peer_id,
          data: { ice: event.candidate }
        }));
      }
    };

    pc.ontrack = (event) => {
      console.log("[WebRTC] Received remote track stream:", event.streams[0]);
      if (event.streams && event.streams[0]) {
        setRemoteStream(event.streams[0]);
      }
    };

    pc.oniceconnectionstatechange = () => {
      console.log("[WebRTC] ICE Connection State changed:", pc.iceConnectionState);
    };

    const createAndSendOffer = async () => {
      try {
        console.log("[WebRTC] Creating local SDP offer...");
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        console.log("[WebRTC] Sending offer to peer:", activeCall.peer_id);
        ws.send(JSON.stringify({
          event: 'signal',
          to_user_id: activeCall.peer_id,
          data: { sdp: pc.localDescription }
        }));
      } catch (err) {
        console.error("[WebRTC] Failed to create and send offer:", err);
      }
    };

    // Add local media tracks
    if (localStream) {
      console.log("[WebRTC] Adding local stream tracks to connection");
      localStream.getTracks().forEach(track => {
        pc.addTrack(track, localStream);
      });
      if (activeCall.role === 'doctor') {
        createAndSendOffer();
      }
    } else {
      console.log("[WebRTC] Local stream not ready yet, requesting camera access...");
      startLocalCamera().then(() => {
        if (streamRef.current) {
          console.log("[WebRTC] Local stream acquired. Adding tracks to connection");
          streamRef.current.getTracks().forEach(track => {
            pc.addTrack(track, streamRef.current);
          });
          if (activeCall.role === 'doctor') {
            createAndSendOffer();
          }
        }
      });
    }

    return () => {
      if (peerConnectionRef.current) {
        console.log("[WebRTC] Cleaning up RTCPeerConnection on unmount");
        peerConnectionRef.current.close();
        peerConnectionRef.current = null;
      }
      setRemoteStream(null);
    };
  }, [callStatus, activeCall?.peer_id, activeCall?.role, localStream]);

  // WebRTC Signaling receiver logic
  const handleRemoteSignal = async (fromUserId, data) => {
    const pc = peerConnectionRef.current;
    if (!pc) {
      console.warn("[WebRTC] Received signal but RTCPeerConnection is null");
      return;
    }

    if (data.sdp) {
      const sdp = new RTCSessionDescription(data.sdp);
      console.log(`[WebRTC] Received remote description of type ${sdp.type} from:`, fromUserId);
      try {
        await pc.setRemoteDescription(sdp);
        if (sdp.type === 'offer') {
          console.log("[WebRTC] Creating SDP answer...");
          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          console.log("[WebRTC] Sending SDP answer back to:", fromUserId);
          ws.send(JSON.stringify({
            event: 'signal',
            to_user_id: fromUserId,
            data: { sdp: pc.localDescription }
          }));
        }
      } catch (err) {
        console.error("[WebRTC] Error handling SDP session description:", err);
      }
    } else if (data.ice) {
      console.log("[WebRTC] Received remote ICE candidate from:", fromUserId);
      try {
        await pc.addIceCandidate(new RTCIceCandidate(data.ice));
      } catch (err) {
        console.error("[WebRTC] Error adding remote ICE candidate:", err);
      }
    }
  };

  const handleRemoteSignalRef = useRef(handleRemoteSignal);
  useEffect(() => {
    handleRemoteSignalRef.current = handleRemoteSignal;
  }, [localStream, activeCall, ws]);

  // Subscribe to WS signaling events globally
  useEffect(() => {
    if (!subscribe || !user) return;
    
    const unsubscribe = subscribe((data) => {
      if (data.event === 'call_initiated') {
        setIncomingCall({
          call_id: data.data.call_id,
          room_id: data.data.room_id,
          doctor_name: data.data.doctor_name,
          peer_id: data.data.peer_id
        });
        setCallStatus('ringing');
      } else if (data.event === 'accepted') {
        setActiveCall(prev => prev ? {
          ...prev,
          peer_id: data.data.peer_id
        } : null);
        setCallStatus('connected');
      } else if (data.event === 'rejected') {
        setCallStatus('declined');
        stopLocalCamera();
        setTimeout(() => {
          setActiveCall(null);
          setCallStatus('idle');
        }, 2500);
      } else if (data.event === 'left') {
        setCallStatus('ended');
        stopLocalCamera();
        setTimeout(() => {
          setActiveCall(null);
          setIncomingCall(null);
          setCallStatus('idle');
        }, 2000);
      } else if (data.event === 'signal') {
        if (handleRemoteSignalRef.current) {
          handleRemoteSignalRef.current(data.from_user_id, data.data);
        }
      }
    });
    
    return unsubscribe;
  }, [subscribe, user]);

  useEffect(() => {
    if (!user) {
      stopLocalCamera();
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
              setActiveCall({
                call_id: data.call_id,
                room_id: data.room_id,
                peer_id: data.peer_id,
                role: 'patient',
                otherPartyName: data.other_party_name
              });
              setCallStatus('connected');
            }
          } else if (data.role === 'doctor') {
            setActiveCall({
              call_id: data.call_id,
              room_id: data.room_id,
              peer_id: data.peer_id,
              role: 'doctor',
              otherPartyName: data.other_party_name
            });
            if (data.status === 'INITIATED' || data.status === 'RINGING') {
              setCallStatus('ringing');
            } else {
              setCallStatus('connected');
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
