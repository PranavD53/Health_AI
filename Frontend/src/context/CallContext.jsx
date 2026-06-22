import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
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
  const [callDuration, setCallDuration] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);
  
  const localVideoRef = useRef(null);
  const streamRef = useRef(null);

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
    let ringTimeout = null;
    if (callStatus === 'ringing' && activeCall && activeCall.role === 'doctor') {
      ringTimeout = setTimeout(() => {
        console.log("Ringing timed out. Ending call as MISSED.");
        handleEndCall();
      }, 30000); // 30 seconds
    }
    return () => {
      if (ringTimeout) {
        clearTimeout(ringTimeout);
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
              startLocalCamera();
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
            startLocalCamera();
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
        startLocalCamera();
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
      callDuration,
      isMuted,
      isVideoOff,
      localVideoRef,
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
