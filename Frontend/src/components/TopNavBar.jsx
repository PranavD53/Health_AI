import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { api } from '../services/api';

export default function TopNavBar() {
  const { currentLanguage, setCurrentLanguage, t } = useLanguage();
  const { user, logout } = useAuth();
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [profileData, setProfileData] = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [previousNotificationCount, setPreviousNotificationCount] = useState(0);

  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('theme') || 'light';
  });

  const [tarsVoiceEnabled, setTarsVoiceEnabled] = useState(() => {
    return localStorage.getItem('tars_voice_enabled') !== 'false';
  });

  const toggleTarsVoice = () => {
    const newVal = !tarsVoiceEnabled;
    setTarsVoiceEnabled(newVal);
    localStorage.setItem('tars_voice_enabled', newVal ? 'true' : 'false');
    window.dispatchEvent(new Event('tars_voice_toggle'));
  };

  useEffect(() => {
    const handleStorageChange = () => {
      setTarsVoiceEnabled(localStorage.getItem('tars_voice_enabled') !== 'false');
    };
    window.addEventListener('tars_voice_toggle', handleStorageChange);
    window.addEventListener('storage', handleStorageChange);
    return () => {
      window.removeEventListener('tars_voice_toggle', handleStorageChange);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  const playNotificationSound = () => {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const now = audioCtx.currentTime;
      
      // First chime (higher pitch)
      const osc1 = audioCtx.createOscillator();
      const gain1 = audioCtx.createGain();
      osc1.connect(gain1);
      gain1.connect(audioCtx.destination);
      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(880, now); // A5
      gain1.gain.setValueAtTime(0, now);
      gain1.gain.linearRampToValueAtTime(0.15, now + 0.02);
      gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
      osc1.start(now);
      osc1.stop(now + 0.2);
      
      // Second chime (slightly lower, creating a pleasant double-chime effect)
      const osc2 = audioCtx.createOscillator();
      const gain2 = audioCtx.createGain();
      osc2.connect(gain2);
      gain2.connect(audioCtx.destination);
      osc2.type = 'sine';
      osc2.frequency.setValueAtTime(784, now + 0.15); // G5
      gain2.gain.setValueAtTime(0, now + 0.15);
      gain2.gain.linearRampToValueAtTime(0.15, now + 0.17);
      gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
      osc2.start(now + 0.15);
      osc2.stop(now + 0.35);
    } catch (e) {
      console.warn("Notification sound failed:", e);
    }
  };

  const loadProfile = async () => {
    if (!user) return;
    setLoadingProfile(true);
    try {
      if (user.role === 'patient') {
        const data = await api.getProfile();
        setProfileData(data);
      } else if (user.role === 'doctor') {
        // Find doctor details
        const docList = await api.getDoctors();
        const doc = docList.find(d => d.user_id === user.id);
        if (doc) {
          setProfileData(doc);
        } else {
          setProfileData({ name: "Dr. Doctor", contact: user.email, specialization: "General" });
        }
      } else {
        setProfileData({ name: "Administrator", role: "admin", contact: user.email });
      }
    } catch (err) {
      console.error("Failed to load profile for top navbar:", err);
      // Fallback
      setProfileData({ name: user.email.split('@')[0], contact: user.email });
    } finally {
      setLoadingProfile(false);
    }
  };

  const fetchNotifications = async () => {
    if (!user) return;
    try {
      const data = await api.getNotifications();
      setNotifications(data);
      
      // Play notification sound if new notifications arrived
      if (data.length > previousNotificationCount && previousNotificationCount !== 0) {
        playNotificationSound();
      }
      setPreviousNotificationCount(data.length);
    } catch (err) {
      console.error("Failed to fetch notifications:", err);
    }
  };

  const handleMarkAsRead = async (notifId) => {
    try {
      await api.markNotificationRead(notifId);
      setNotifications(prev => prev.filter(n => n.id !== notifId));
    } catch (err) {
      console.error("Failed to mark notification as read:", err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.markAllNotificationsRead();
      setNotifications([]);
    } catch (err) {
      console.error("Failed to mark all notifications as read:", err);
    }
  };

  useEffect(() => {
    loadProfile();
  }, [user]);

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 10000);
    return () => clearInterval(interval);
  }, [user]);

  return (
    <>
      <header className="fixed top-0 left-0 w-full z-50 flex justify-between items-center px-margin-desktop h-16 bg-surface border-b border-outline-variant/30 shadow-sm">
        <div className="flex items-center gap-xl">
          <span className="text-title-md font-bold text-primary tracking-tight">HealthAI</span>
        </div>
        
        <div className="flex items-center gap-md">
          {/* Language Selector Dropdown */}
          <div className="flex items-center">
            <select
              value={currentLanguage}
              onChange={(e) => setCurrentLanguage(e.target.value)}
              className="text-xs border border-outline-variant/60 rounded-xl px-2 py-1 bg-surface font-semibold text-primary focus:outline-none transition-colors hover:border-primary cursor-pointer"
            >
              <option value="en">English</option>
              <option value="hi">Hindi (हिन्दी)</option>
              <option value="te">Telugu (తెలుగు)</option>
            </select>
          </div>

          {/* TARS Global Toggle Switch */}
          <button
            onClick={toggleTarsVoice}
            className={`p-2 rounded-full transition-all duration-300 focus:outline-none flex items-center justify-center relative hover:bg-surface-container-high active:scale-95 ${
              tarsVoiceEnabled ? 'text-emerald-500 hover:text-emerald-600' : 'text-outline hover:text-primary'
            }`}
            title={tarsVoiceEnabled ? "Disable TARS Global Voice Wake-up" : "Enable TARS Global Voice Wake-up"}
          >
            {tarsVoiceEnabled && (
              <span className="absolute -inset-0.5 rounded-full border border-emerald-500 animate-ping opacity-40 pointer-events-none"></span>
            )}
            <span className="material-symbols-outlined text-[22px]">
              {tarsVoiceEnabled ? 'mic' : 'mic_off'}
            </span>
          </button>

          {/* Theme Toggle Button */}
          <button
            onClick={toggleTheme}
            className="p-2 text-on-surface-variant hover:text-primary transition-all duration-300 focus:outline-none rounded-full hover:bg-surface-container-high active:scale-95 flex items-center justify-center"
            title={theme === 'light' ? "Switch to Dark Mode" : "Switch to Light Mode"}
          >
            <span className="material-symbols-outlined text-[22px] transition-transform duration-500 hover:rotate-[30deg]">
              {theme === 'light' ? 'dark_mode' : 'light_mode'}
            </span>
          </button>

          {/* Notifications button */}
          <div className="relative">
            <button 
              onClick={() => setNotificationsOpen(!notificationsOpen)}
              className="p-2 text-on-surface-variant hover:text-primary transition-colors focus:outline-none relative"
            >
              <span className="material-symbols-outlined">notifications</span>
              {notifications.length > 0 && (
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-error rounded-full" />
              )}
            </button>
            
            {notificationsOpen && (
              <div className="absolute right-0 mt-2 w-80 bg-white border border-outline-variant rounded-xl shadow-xl z-50 overflow-hidden">
                <div className="p-3 border-b border-outline-variant bg-surface flex justify-between items-center">
                  <h4 className="font-bold text-primary text-label-md">Notifications</h4>
                  {notifications.length > 0 && (
                    <button
                      onClick={handleMarkAllRead}
                      className="text-xs text-secondary hover:text-primary transition-colors font-semibold focus:outline-none"
                    >
                      Mark all read
                    </button>
                  )}
                </div>
                <div className="divide-y divide-outline-variant max-h-60 overflow-y-auto">
                  {notifications.length === 0 ? (
                    <div className="p-4 text-center text-outline text-sm">
                      No new notifications
                    </div>
                  ) : (
                    notifications.map(n => {
                      let iconName = 'notifications';
                      if (n.notification_type === 'chat_message') iconName = 'chat';
                      else if (n.notification_type === 'complaint_submitted') iconName = 'report_problem';
                      else if (n.notification_type === 'complaint_resolved') iconName = 'check_circle';

                      return (
                        <div 
                          key={n.id} 
                          className="p-3 hover:bg-surface-container-low transition-colors flex items-start gap-sm cursor-pointer"
                          onClick={() => {
                            handleMarkAsRead(n.id);
                            if (n.notification_type === 'chat_message') {
                              window.location.href = '/chat';
                            }
                          }}
                        >
                          <span className="material-symbols-outlined text-secondary text-md mt-0.5">{iconName}</span>
                          <div className="flex-1 min-w-0">
                            <p className="text-body-md text-on-surface text-xs leading-normal break-words">{n.message}</p>
                            <span className="text-[10px] text-outline block mt-0.5">
                              {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleMarkAsRead(n.id);
                            }}
                            className="p-0.5 hover:bg-surface-container-high rounded-full text-outline hover:text-on-surface transition-colors focus:outline-none"
                            title="Dismiss"
                          >
                            <span className="material-symbols-outlined text-sm">close</span>
                          </button>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            )}
          </div>

          <div 
            onClick={() => setProfileModalOpen(true)}
            className="flex items-center gap-sm cursor-pointer hover:opacity-85 transition-opacity"
          >
            <div className="w-10 h-10 rounded-full overflow-hidden border border-outline-variant bg-surface-container-low flex items-center justify-center">
              {profileData?.profile_picture ? (
                <img 
                  alt="Profile" 
                  src={profileData.profile_picture.startsWith('http') ? profileData.profile_picture : `http://127.0.0.1:8000${profileData.profile_picture}`} 
                  className="w-full h-full object-cover"
                />
              ) : (
                <span className="material-symbols-outlined text-outline">person</span>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Profile Details Modal */}
      {profileModalOpen && (
        <div className="fixed inset-0 bg-primary/20 backdrop-blur-sm flex items-center justify-center z-[100] animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl w-full max-w-md border border-outline-variant shadow-2xl overflow-hidden">
            <div className="p-6 border-b border-outline-variant bg-surface flex justify-between items-center">
              <h3 className="font-headline-lg text-title-md text-primary flex items-center gap-xs">
                <span className="material-symbols-outlined text-secondary">account_circle</span>
                User Profile
              </h3>
              <button 
                onClick={() => setProfileModalOpen(false)}
                className="p-1 hover:bg-surface-container-high rounded-full transition-colors text-outline focus:outline-none"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            
            <div className="p-6 space-y-4">
              {loadingProfile ? (
                <div className="flex flex-col items-center py-8 space-y-2">
                  <div className="w-8 h-8 border-4 border-secondary border-t-transparent rounded-full animate-spin"></div>
                  <p className="text-label-sm text-outline">Loading profile details...</p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center gap-md pb-4 border-b border-outline-variant/30">
                    <div className="w-16 h-16 rounded-full overflow-hidden border border-outline-variant bg-surface-container flex items-center justify-center">
                      {profileData?.profile_picture ? (
                        <img 
                          alt="Avatar" 
                          src={profileData.profile_picture.startsWith('http') ? profileData.profile_picture : `http://127.0.0.1:8000${profileData.profile_picture}`} 
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <span className="material-symbols-outlined text-3xl text-outline">person</span>
                      )}
                    </div>
                    <div>
                      <h4 className="font-bold text-on-surface text-lg">{profileData?.name || "No name configured"}</h4>
                      <p className="text-label-sm text-outline capitalize">Role: {user?.role}</p>
                      <p className="text-label-sm text-secondary">{user?.email}</p>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {user?.role === 'patient' && (
                      <>
                        <div>
                          <span className="text-label-sm text-outline block">Date of Birth</span>
                          <span className="text-body-md text-on-surface">{profileData?.date_of_birth || "Not specified"}</span>
                        </div>
                        <div>
                          <span className="text-label-sm text-outline block">Gender</span>
                          <span className="text-body-md text-on-surface">{profileData?.gender || "Not specified"}</span>
                        </div>
                        <div>
                          <span className="text-label-sm text-outline block">Allergies</span>
                          <span className="text-body-md text-on-surface text-error font-medium">{profileData?.allergies || "None reported"}</span>
                        </div>
                        <div>
                          <span className="text-label-sm text-outline block">Medical Conditions</span>
                          <span className="text-body-md text-on-surface">{profileData?.existing_conditions || "None reported"}</span>
                        </div>
                      </>
                    )}

                    {user?.role === 'doctor' && (
                      <>
                        <div>
                          <span className="text-label-sm text-outline block">Specialization</span>
                          <span className="text-body-md text-on-surface font-semibold text-secondary">{profileData?.specialization}</span>
                        </div>
                        <div>
                          <span className="text-label-sm text-outline block">Years of Experience</span>
                          <span className="text-body-md text-on-surface">{profileData?.experience_years} years</span>
                        </div>
                      </>
                    )}

                    <div>
                      <span className="text-label-sm text-outline block">Clinic / Home Address</span>
                      <span className="text-body-md text-on-surface">{profileData?.address || "No address provided"}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="p-4 bg-surface border-t border-outline-variant flex gap-md">
              <button 
                onClick={() => {
                  setProfileModalOpen(false);
                  window.location.href = '/settings';
                }}
                className="flex-1 bg-secondary-container hover:bg-secondary-container/80 text-on-secondary-container py-2.5 rounded-lg font-bold text-label-md text-center transition-colors"
              >
                Edit Profile
              </button>
              <button 
                onClick={logout}
                className="flex-1 bg-error/10 hover:bg-error/15 text-error py-2.5 rounded-lg font-bold text-label-md text-center transition-colors"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
