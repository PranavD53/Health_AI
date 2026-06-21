import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { useWebSocket } from '../context/WebSocketContext';
import { api } from '../services/api';

export default function SideNavBar() {
  const { t } = useLanguage();
  const { user, logout, checkAuth } = useAuth();
  const location = useLocation();
  const [sosLoading, setSosLoading] = useState(false);
  const [sosSuccess, setSosSuccess] = useState(false);
  const [activeAlertsCount, setActiveAlertsCount] = useState(0);
  const [switching, setSwitching] = useState(false);

  const { subscribe } = useWebSocket() || {};

  // For doctors: poll or check active emergency alerts
  useEffect(() => {
    if (user && (user.role === 'doctor' || user.role === 'admin')) {
      const fetchAlerts = async () => {
        try {
          const alerts = await api.getEmergencyAlerts();
          setActiveAlertsCount(alerts.length);
        } catch (e) {
          console.error(e);
        }
      };
      fetchAlerts();
    }
  }, [user]);

  useEffect(() => {
    if (!subscribe || !user || (user.role !== 'doctor' && user.role !== 'admin')) return;
    const unsubscribe = subscribe((data) => {
      if (data.event === 'new_alert') {
        api.getEmergencyAlerts().then(alerts => setActiveAlertsCount(alerts.length)).catch(console.error);
      }
    });
    return unsubscribe;
  }, [subscribe, user]);

  const handleSos = async () => {
    setSosLoading(true);
    const triggerWithCoords = async (lat = null, lng = null) => {
      try {
        await api.triggerSOS(null, lat, lng);
        setSosSuccess(true);
        setTimeout(() => setSosSuccess(false), 5000);
      } catch (e) {
        alert("SOS Trigger failed: " + e.message);
      } finally {
        setSosLoading(false);
      }
    };

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const lat = position.coords.latitude;
          const lng = position.coords.longitude;
          triggerWithCoords(lat, lng);
        },
        (error) => {
          console.warn("Geolocation failed or denied, sending SOS without coordinates.", error);
          triggerWithCoords(null, null);
        },
        { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
      );
    } else {
      console.warn("Geolocation not supported by browser, sending SOS without coordinates.");
      triggerWithCoords(null, null);
    }
  };

  const handleRoleSwitch = async () => {
    setSwitching(true);
    try {
      const res = await api.switchRole();
      await checkAuth();
      const targetId = res.role === 'doctor' ? res.doctor_profile_id : user.id;
      window.location.href = `/${res.role}/${targetId}`;
    } catch (err) {
      alert("Failed to switch role: " + err.message);
    } finally {
      setSwitching(false);
    }
  };

  const isActive = (path) => location.pathname === path;

  const getLinkClass = (path) => {
    return `flex items-center gap-md px-4 py-3 rounded-lg transition-all duration-150 ${
      isActive(path)
        ? 'bg-secondary-container text-on-secondary-container font-bold scale-[0.98]'
        : 'text-on-surface-variant hover:bg-surface-container-high'
    }`;
  };

  return (
    <>
      <aside className="hidden lg:flex flex-col fixed left-0 top-16 h-[calc(100vh-64px)] p-md w-64 z-40 bg-surface-container-low border-r border-outline-variant/30">
        <div className="mb-xl flex items-center gap-md px-2">
          <div className="w-10 h-10 rounded-lg bg-primary-fixed flex items-center justify-center text-primary shadow-sm">
            <span className="material-symbols-outlined text-[24px]">health_and_safety</span>
          </div>
          <div>
            <p className="text-label-md font-bold text-primary">{t('assistant')}</p>
            <p className="text-label-sm text-outline capitalize">{t('role')}: {user?.role}</p>
          </div>
        </div>

        <nav className="flex-1 flex flex-col gap-sm">
          {/* Patient navigation links */}
          {user?.role === 'patient' && (
            <>
              <Link to={`/patient/${user.id}`} className={getLinkClass(`/patient/${user.id}`)}>
                <span className="material-symbols-outlined">dashboard</span>
                <span className="text-label-md">{t('dashboard')}</span>
              </Link>
              <Link to="/appointments" className={getLinkClass('/appointments')}>
                <span className="material-symbols-outlined">event</span>
                <span className="text-label-md">{t('appointments')}</span>
              </Link>
              <Link to="/records" className={getLinkClass('/records')}>
                <span className="material-symbols-outlined">description</span>
                <span className="text-label-md">{t('records')}</span>
              </Link>
              <Link to="/chat" className={getLinkClass('/chat')}>
                <span className="material-symbols-outlined">chat</span>
                <span className="text-label-md">{t('chat')}</span>
              </Link>
              <Link to="/settings" className={getLinkClass('/settings')}>
                <span className="material-symbols-outlined">settings</span>
                <span className="text-label-md">{t('settings')}</span>
              </Link>
            </>
          )}

          {/* Doctor navigation links */}
          {user?.role === 'doctor' && (
            <>
              <Link to={`/doctor/${user.doctor_profile_id}`} className={getLinkClass(`/doctor/${user.doctor_profile_id}`)}>
                <span className="material-symbols-outlined">dashboard</span>
                <span className="text-label-md">{t('workspace')}</span>
                {activeAlertsCount > 0 && (
                  <span className="ml-auto bg-error text-on-error text-[10px] font-bold px-2 py-0.5 rounded-full animate-pulse">
                    {activeAlertsCount} SOS
                  </span>
                )}
              </Link>
              <Link to="/chat" className={getLinkClass('/chat')}>
                <span className="material-symbols-outlined">chat</span>
                <span className="text-label-md">{t('chat')}</span>
              </Link>
              <Link to="/settings" className={getLinkClass('/settings')}>
                <span className="material-symbols-outlined">settings</span>
                <span className="text-label-md">{t('settings')}</span>
              </Link>
            </>
          )}

          {/* Admin navigation links */}
          {user?.role === 'admin' && (
            <>
              <Link to={`/admin/${user.id}`} className={getLinkClass(`/admin/${user.id}`)}>
                <span className="material-symbols-outlined">admin_panel_settings</span>
                <span className="text-label-md">{t('adminPortal')}</span>
              </Link>
              <Link to="/chat" className={getLinkClass('/chat')}>
                <span className="material-symbols-outlined">chat</span>
                <span className="text-label-md">{t('chat')}</span>
              </Link>
              <Link to="/settings" className={getLinkClass('/settings')}>
                <span className="material-symbols-outlined">settings</span>
                <span className="text-label-md">{t('settings')}</span>
              </Link>
            </>
          )}
        </nav>

        <div className="mt-auto pt-lg flex flex-col gap-sm border-t border-outline-variant/30">
          {user?.role === 'patient' && (
            <button 
              onClick={handleSos}
              disabled={sosLoading}
              className={`w-full text-on-error py-3 rounded-lg font-bold text-label-md flex items-center justify-center gap-sm mb-lg shadow-md active:scale-95 transition-all ${
                sosSuccess ? 'bg-success' : 'bg-error hover:bg-error/95'
              }`}
            >
              <span className="material-symbols-outlined animate-pulse">emergency</span> 
              {sosLoading ? 'Triggering...' : sosSuccess ? 'SOS Alert Sent!' : t('sosTrigger')}
            </button>
          )}

          {user?.has_admin_permission && !(user.role === 'admin' && user.base_role !== 'doctor' && user.base_role !== 'caregiver') && (
            <button 
              onClick={handleRoleSwitch}
              disabled={switching}
              className="flex items-center gap-md px-4 py-2 bg-primary/10 hover:bg-primary/15 text-primary rounded-lg transition-colors text-left focus:outline-none w-full font-bold mb-xs"
            >
              <span className="material-symbols-outlined">swap_horiz</span>
              <span className="text-label-md">
                {switching ? 'Switching...' : user.role === 'admin' 
                  ? (user.base_role === 'doctor' ? t('switchToDoctor') : user.base_role === 'caregiver' ? t('switchToCaregiver') : t('switchToUser')) 
                  : t('switchToAdmin')}
              </span>
            </button>
          )}

          <button 
            onClick={logout}
            className="flex items-center gap-md px-4 py-2 text-on-surface-variant hover:bg-surface-container-high rounded-lg transition-colors text-left focus:outline-none w-full"
          >
            <span className="material-symbols-outlined">logout</span>
            <span className="text-label-md">{t('logout')}</span>
          </button>
        </div>
      </aside>

      {/* Floating Success Banner for SOS */}
      {sosSuccess && (
        <div className="fixed bottom-6 right-6 bg-error text-on-error px-6 py-4 rounded-xl shadow-2xl z-[110] flex items-center gap-md animate-in slide-in-from-bottom-6 duration-300">
          <span className="material-symbols-outlined text-[32px] animate-bounce">warning</span>
          <div>
            <h4 className="font-bold">Emergency SOS Triggered!</h4>
            <p className="text-xs opacity-90">Your address and medical summary have been broadcast to all nearby doctors.</p>
          </div>
        </div>
      )}
    </>
  );
}
