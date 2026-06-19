import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useCall } from '../context/CallContext';
import TopNavBar from './TopNavBar';
import SideNavBar from './SideNavBar';
import GlobalAssistant from './GlobalAssistant';
import { applyTheme } from '../utils/theme';

export default function Layout({ children }) {
  const { user, isVerified, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const {
    activeCall,
    incomingCall,
    callStatus,
    localStream,
    callDuration,
    isMuted,
    isVideoOff,
    localVideoRef,
    handleAcceptCall,
    handleRejectCall,
    handleEndCall,
    toggleMute,
    toggleVideo
  } = useCall();

  const getInitials = (name) => {
    if (!name) return '';
    return name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
  };

  const formatTime = (secs) => {
    const mins = Math.floor(secs / 60);
    const remaining = secs % 60;
    return `${mins.toString().padStart(2, '0')}:${remaining.toString().padStart(2, '0')}`;
  };

  useEffect(() => {
    if (!loading) {
      if (!user) {
        navigate('/login');
      } else if (!isVerified && location.pathname !== '/otp-verify') {
        navigate('/otp-verify');
      }
    }
  }, [user, isVerified, loading, navigate, location.pathname]);

  // Global Theme event listener sync
  useEffect(() => {
    const handleThemeChange = () => {
      const activeTheme = localStorage.getItem('theme') || 'light';
      applyTheme(activeTheme);
    };
    handleThemeChange();
    
    window.addEventListener('theme_change', handleThemeChange);
    return () => {
      window.removeEventListener('theme_change', handleThemeChange);
    };
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center space-y-4">
        <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
        <p className="text-primary font-bold">HealthAI is loading...</p>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background relative overflow-x-hidden transition-colors duration-300">
      <TopNavBar />
      <div className="flex pt-16 relative z-10">
        <SideNavBar />
        <main className="flex-1 lg:pl-72 min-h-[calc(100vh-64px)] p-margin-mobile md:p-gutter">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
      {/* Premium floating network decoration */}
      <div className="absolute bottom-10 right-12 w-32 h-16 pointer-events-none z-0 opacity-20 hidden md:block select-none">
        <svg className="w-full h-full text-primary" viewBox="0 0 100 50">
          <line x1="20" y1="25" x2="80" y2="25" stroke="currentColor" strokeWidth="0.8" strokeDasharray="3,3" />
          <circle cx="20" cy="25" r="4" fill="currentColor" className="animate-pulse" />
          <circle cx="80" cy="25" r="4" fill="currentColor" className="animate-pulse" style={{ animationDelay: '0.5s' }} />
        </svg>
      </div>
      <GlobalAssistant />

      {/* 1. Incoming Call Ringing Overlay for Patient */}
      {incomingCall && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center z-[9999] animate-in fade-in duration-300">
          <div className="bg-surface-container-highest border border-outline-variant/30 rounded-3xl p-8 w-full max-w-sm text-center shadow-2xl flex flex-col items-center gap-md scale-in">
            <div className="relative flex items-center justify-center my-4">
              <div className="absolute w-24 h-24 bg-success/20 rounded-full animate-ping duration-1000"></div>
              <div className="absolute w-20 h-20 bg-success/30 rounded-full animate-pulse duration-1000"></div>
              <div className="w-16 h-16 bg-success text-white rounded-full flex items-center justify-center text-xl font-bold z-10 shadow-lg">
                {getInitials(incomingCall.doctor_name)}
              </div>
            </div>

            <div>
              <span className="text-[10px] bg-success-container text-on-success-container px-3 py-1 rounded-full font-bold uppercase tracking-wider animate-pulse">
                Incoming Video Call
              </span>
              <h3 className="text-lg font-black text-on-surface mt-3">{incomingCall.doctor_name}</h3>
              <p className="text-xs text-outline mt-1">is inviting you to a secure video consultation...</p>
            </div>

            <div className="flex items-center gap-xl mt-4 w-full justify-center">
              <button
                type="button"
                onClick={handleRejectCall}
                className="w-14 h-14 rounded-full bg-error hover:bg-error-container text-white flex items-center justify-center shadow-lg hover:shadow-error/30 active:scale-90 transition-all focus:outline-none"
                title="Decline Call"
              >
                <span className="material-symbols-outlined text-lg">call_end</span>
              </button>
              <button
                type="button"
                onClick={handleAcceptCall}
                className="w-14 h-14 rounded-full bg-success hover:bg-success-container text-white flex items-center justify-center shadow-lg hover:shadow-success/30 active:scale-90 transition-all focus:outline-none"
                title="Accept Call"
              >
                <span className="material-symbols-outlined text-lg">videocam</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 2. Active Video Call Window (Ongoing/Ringing Outbound) */}
      {activeCall && (
        <div className="fixed inset-0 bg-slate-950/95 flex flex-col justify-between z-[9999] animate-in fade-in duration-300 text-white">
          <div className="px-6 py-4 flex items-center justify-between border-b border-white/10 bg-slate-900/60 backdrop-blur-md">
            <div className="flex items-center gap-md">
              <span className="w-2.5 h-2.5 rounded-full bg-success animate-pulse"></span>
              <h3 className="font-bold text-sm tracking-wide">Telehealth Video Call</h3>
            </div>
            
            <div className="flex items-center gap-md">
              {callStatus === 'connected' && (
                <span className="text-xs font-mono bg-white/10 px-3 py-1 rounded-full text-slate-300">
                  {formatTime(callDuration)}
                </span>
              )}
              <span className="text-xs text-slate-400 capitalize font-semibold bg-white/5 px-3 py-1 rounded-full">
                {activeCall.role} Mode
              </span>
            </div>
          </div>

          <div className="flex-1 relative flex items-center justify-center p-6 bg-slate-900">
            <div className="w-full h-full max-w-5xl rounded-2xl overflow-hidden bg-slate-800 border border-white/5 flex flex-col items-center justify-center relative shadow-inner">
              {callStatus === 'ringing' ? (
                <div className="text-center flex flex-col items-center gap-md animate-pulse">
                  <div className="w-20 h-20 bg-primary/20 text-primary border border-primary/30 rounded-full flex items-center justify-center text-2xl font-bold animate-bounce mb-2">
                    {getInitials(activeCall.otherPartyName)}
                  </div>
                  <h4 className="text-lg font-bold text-white">Calling {activeCall.otherPartyName}...</h4>
                  <p className="text-xs text-slate-400">Waiting for patient to accept the invitation</p>
                </div>
              ) : callStatus === 'declined' ? (
                <div className="text-center flex flex-col items-center gap-md text-error">
                  <span className="material-symbols-outlined text-4xl animate-bounce">call_end</span>
                  <h4 className="text-lg font-bold text-error">Call Declined</h4>
                  <p className="text-xs text-slate-400">The patient declined your video consultation invitation.</p>
                </div>
              ) : callStatus === 'ended' ? (
                <div className="text-center flex flex-col items-center gap-md text-slate-300">
                  <span className="material-symbols-outlined text-4xl">do_not_disturb_on</span>
                  <h4 className="text-lg font-bold">Call Ended</h4>
                  <p className="text-xs text-slate-400">The video consultation has been completed.</p>
                </div>
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center bg-slate-900 relative">
                  <div className="relative flex items-center justify-center mb-6">
                    <div className="absolute w-32 h-32 bg-primary/10 rounded-full animate-ping duration-[3000ms]"></div>
                    <div className="absolute w-28 h-28 bg-primary/20 rounded-full animate-pulse duration-[2000ms]"></div>
                    <div className="w-24 h-24 rounded-full bg-slate-800 border-2 border-primary/30 flex items-center justify-center text-2xl font-bold text-primary z-10 shadow-lg">
                      {getInitials(activeCall.otherPartyName)}
                    </div>
                  </div>
                  
                  <div className="z-10 text-center">
                    <h4 className="text-lg font-black text-white">{activeCall.otherPartyName}</h4>
                    <p className="text-xs text-slate-400 mt-1 flex items-center justify-center gap-sm">
                      <span className="w-1.5 h-1.5 rounded-full bg-success animate-ping"></span>
                      <span>Connected & Streaming Securely</span>
                    </p>
                  </div>

                  <div className="absolute bottom-6 flex items-end gap-[4px] h-8 justify-center w-full opacity-60">
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15].map(i => {
                      const randHeight = [12, 28, 16, 24, 8, 32, 20, 14, 26, 18, 10, 22, 15, 27, 9][i % 15];
                      const randDur = [1.2, 0.8, 1.5, 0.9, 1.1, 1.4, 0.7, 1.3, 1.0, 1.2, 0.9, 1.4, 0.8, 1.1, 1.3][i % 15];
                      return (
                        <div 
                          key={i} 
                          className="w-[3px] bg-primary rounded-full animate-pulse" 
                          style={{
                            height: `${randHeight}px`,
                            animationDuration: `${randDur}s`,
                            animationIterationCount: 'infinite'
                          }}
                        />
                      );
                    })}
                  </div>
                </div>
              )}

              {localStream && (
                <div className="absolute bottom-4 right-4 w-40 h-52 md:w-48 md:h-64 rounded-xl border border-white/20 overflow-hidden shadow-2xl bg-black z-20 transition-all transform hover:scale-[1.02]">
                  {isVideoOff ? (
                    <div className="w-full h-full flex flex-col items-center justify-center bg-slate-900 text-slate-400 text-center p-2">
                      <span className="material-symbols-outlined text-lg mb-1">videocam_off</span>
                      <span className="text-[10px] font-bold uppercase tracking-wider">Camera Off</span>
                    </div>
                  ) : (
                    <video
                      ref={localVideoRef}
                      autoPlay
                      playsInline
                      muted
                      className="w-full h-full object-cover scale-x-[-1]"
                    />
                  )}
                  <div className="absolute bottom-2 left-2 bg-slate-950/70 backdrop-blur-md px-2 py-0.5 rounded text-[9px] font-bold text-white uppercase tracking-wide">
                    You
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="py-6 flex flex-col md:flex-row items-center justify-center gap-md border-t border-white/10 bg-slate-900/60 backdrop-blur-md w-full">
            <div className="flex items-center gap-lg">
              <button
                type="button"
                onClick={toggleMute}
                disabled={callStatus !== 'connected'}
                className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${
                  isMuted 
                    ? 'bg-error hover:bg-error-container text-white' 
                    : 'bg-white/10 hover:bg-white/20 text-white active:scale-95'
                } disabled:opacity-50`}
                title={isMuted ? "Unmute Mic" : "Mute Mic"}
              >
                <span className="material-symbols-outlined text-lg">
                  {isMuted ? 'mic_off' : 'mic'}
                </span>
              </button>

              <button
                type="button"
                onClick={toggleVideo}
                disabled={callStatus !== 'connected'}
                className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${
                  isVideoOff 
                    ? 'bg-error hover:bg-error-container text-white' 
                    : 'bg-white/10 hover:bg-white/20 text-white active:scale-95'
                } disabled:opacity-50`}
                title={isVideoOff ? "Turn Video On" : "Turn Video Off"}
              >
                <span className="material-symbols-outlined text-lg">
                  {isVideoOff ? 'videocam_off' : 'videocam'}
                </span>
              </button>

              <button
                type="button"
                onClick={handleEndCall}
                className="w-16 h-12 px-6 rounded-full bg-error hover:bg-error-container text-white flex items-center justify-center shadow-lg hover:shadow-error/30 active:scale-95 transition-all"
                title="End Consultation"
              >
                <span className="material-symbols-outlined text-lg">call_end</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
