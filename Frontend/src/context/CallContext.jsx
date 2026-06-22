import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { Room, RoomEvent } from 'livekit-client';
import { api } from '../services/api';
import { useWebSocket } from './WebSocketContext';
import { useAuth } from './AuthContext';

const CallContext = createContext(null);

export function CallProvider({ children }) {
  const { user } = useAuth();
  const { subscribe } = useWebSocket() || {};

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
  const roomRef = useRef(null);
  const ringTimeoutRef = useRef(null);

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

  const toggleMute = async () => {
    if (roomRef.current) {
      const isMutedNow = !roomRef.current.localParticipant.isMicrophoneEnabled;
      await roomRef.current.localParticipant.setMicrophoneEnabled(!isMutedNow);
      setIsMuted(isMutedNow);
    } else if (streamRef.current) {
      const audioTrack = streamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        setIsMuted(!audioTrack.enabled);
      }
    }
  };

  const toggleVideo = async () => {
    if (roomRef.current) {
      const isVideoOffNow = !roomRef.current.localParticipant.isCameraEnabled;
      await roomRef.current.localParticipant.setCameraEnabled(!isVideoOffNow);
      setIsVideoOff(isVideoOffNow);
    } else if (streamRef.current) {
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
        token: res.token,
        sfu_url: res.sfu_url
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
        token: res.token,
        sfu_url: res.sfu_url,
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
    
    if (roomRef.current) {
      try {
        roomRef.current.disconnect();
      } catch (e) {
        console.error("Error disconnecting LiveKit room:", e);
      }
      roomRef.current = null;
    }
    
    setRemoteStream(null);

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

  useEffect(() => {
    if (callStatus === 'ringing' && activeCall && activeCall.role === 'doctor') {
      if (ringTimeoutRef.current) {
        clearTimeout(ringTimeoutRef.current);
      }
      ringTimeoutRef.current = setTimeout(() => {
        console.log("Ringing timed out. Ending call as MISSED.");
        handleEndCall();
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

  // LiveKit WebRTC SFU Room Connection Effect
  useEffect(() => {
    let activeRoom = null;

    if (callStatus === 'connected' && activeCall?.token && activeCall?.sfu_url) {
      const connectRoom = async () => {
        try {
          console.log(`[WebRTC] Connecting to LiveKit room at ${activeCall.sfu_url}...`);
          const room = new Room({
            adaptiveStream: true,
            dynacast: true,
          });
          activeRoom = room;
          roomRef.current = room;

          room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
            console.log(`[WebRTC] Track subscribed: ${track.kind} from ${participant.identity}`);
            if (track.kind === 'video') {
              const stream = new MediaStream([track.mediaStreamTrack]);
              setRemoteStream(stream);
            } else if (track.kind === 'audio') {
              const el = track.attach();
              document.body.appendChild(el);
            }
          });

          room.on(RoomEvent.TrackUnsubscribed, (track, publication, participant) => {
            console.log(`[WebRTC] Track unsubscribed: ${track.kind}`);
            if (track.kind === 'video') {
              setRemoteStream(null);
            } else if (track.kind === 'audio') {
              track.detach();
            }
          });

          room.on(RoomEvent.Disconnected, () => {
            console.log('[WebRTC] Disconnected from LiveKit room');
            setRemoteStream(null);
            stopLocalCamera();
            setActiveCall(null);
            setIncomingCall(null);
            setCallStatus('idle');
          });

          await room.connect(activeCall.sfu_url, activeCall.token);
          console.log('[WebRTC] Connected to LiveKit successfully');

          await room.localParticipant.setCameraEnabled(true);
          await room.localParticipant.setMicrophoneEnabled(true);
          console.log('[WebRTC] Camera and microphone enabled for local participant');

          const localVideoTrack = room.localParticipant.videoTracks.values().next().value?.track;
          if (localVideoTrack && localVideoTrack.mediaStreamTrack) {
            const stream = new MediaStream([localVideoTrack.mediaStreamTrack]);
            setLocalStream(stream);
            streamRef.current = stream;
          }
        } catch (err) {
          console.error('[WebRTC] Failed to connect to LiveKit room:', err);
          // Fallback to local camera if LiveKit connection fails
          startLocalCamera();
        }
      };

      connectRoom();
    }

    return () => {
      if (activeRoom) {
        try {
          activeRoom.disconnect();
        } catch (e) {
          console.error('[WebRTC] Error disconnecting LiveKit room:', e);
        }
        if (roomRef.current === activeRoom) {
          roomRef.current = null;
        }
        setRemoteStream(null);
      }
    };
  }, [callStatus, activeCall?.token, activeCall?.sfu_url]);

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
                doctor_name: data.other_party_name
              });
              setCallStatus('ringing');
            } else if (data.status === 'ACCEPTED' || data.status === 'ONGOING') {
              setActiveCall({
                call_id: data.call_id,
                room_id: data.room_id,
                token: data.token,
                sfu_url: data.sfu_url,
                role: 'patient',
                otherPartyName: data.other_party_name
              });
              setCallStatus('connected');
            }
          } else if (data.role === 'doctor') {
            setActiveCall({
              call_id: data.call_id,
              room_id: data.room_id,
              token: data.token,
              sfu_url: data.sfu_url,
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

  // Subscribe to WS signaling events globally
  useEffect(() => {
    if (!subscribe || !user) return;
    
    const unsubscribe = subscribe((data) => {
      if (data.event === 'call_initiated') {
        // Show incoming call overlay for patient
        setIncomingCall({
          call_id: data.data.call_id,
          room_id: data.data.room_id,
          doctor_name: data.data.doctor_name
        });
        setCallStatus('ringing');
      } else if (data.event === 'accepted') {
        // Connected on doctor side
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
      }
    });
    
    return unsubscribe;
  }, [subscribe, user]);

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
