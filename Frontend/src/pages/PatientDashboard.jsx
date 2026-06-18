import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';

export default function PatientDashboard() {
  const { t, currentLanguage } = useLanguage();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadDashboard = async () => {
    try {
      const data = await api.getPatientDashboard(currentLanguage);
      setDashboardData(data);
    } catch (err) {
      console.error(err);
      setError("Failed to load dashboard data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, [currentLanguage]);

  const handleCancelAppointment = async (apptId) => {
    if (window.confirm("Are you sure you want to cancel this appointment?")) {
      try {
        await api.cancelAppointment(apptId);
        // Reload dashboard
        loadDashboard();
      } catch (err) {
        alert("Failed to cancel: " + err.message);
      }
    }
  };

  if (loading) {
    return (
      <div className="space-y-xl animate-pulse">
        <div className="h-12 bg-surface-container rounded-xl w-1/3"></div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
          <div className="lg:col-span-2 space-y-md">
            <div className="h-64 bg-surface-container rounded-xl"></div>
            <div className="h-48 bg-surface-container rounded-xl"></div>
          </div>
          <div className="h-96 bg-surface-container rounded-xl"></div>
        </div>
      </div>
    );
  }

  // Greeting name
  const greetingName = user?.email.split('@')[0];

  return (
    <div className="space-y-xl animate-in fade-in duration-300">
      {/* Greetings */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-md">
        <div>
          <h2 className="text-on-surface font-headline-lg text-headline-lg">
            {t('welcomeBack')} <span className="text-primary font-bold">{greetingName}</span>
          </h2>
          <p className="text-on-surface-variant font-body-md text-body-md">{t('syncRecords')}</p>
        </div>
        <div className="flex gap-sm">
          <button 
            onClick={() => navigate('/appointments')}
            className="px-4 py-2 bg-primary hover:bg-primary/95 text-white font-bold rounded-lg text-sm transition-colors flex items-center gap-xs shadow-sm active:scale-95 duration-150"
          >
            <span className="material-symbols-outlined text-[18px]">event</span>
            {t('bookVisit')}
          </button>
          <button 
            onClick={() => navigate('/records')}
            className="px-4 py-2 bg-secondary-container hover:bg-secondary-container/90 text-on-secondary-container font-bold rounded-lg text-sm transition-colors flex items-center gap-xs active:scale-95 duration-150"
          >
            <span className="material-symbols-outlined text-[18px]">upload_file</span>
            {t('uploadRecords')}
          </button>
        </div>
      </header>

      {error && (
        <div className="p-4 bg-error-container text-on-error-container rounded-xl flex items-center gap-sm">
          <span className="material-symbols-outlined">error</span>
          <p>{error}</p>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
        {/* Left Side: Appointments & AI Tip */}
        <div className="lg:col-span-2 space-y-lg">
          {/* Upcoming Appointments */}
          <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg interactive-card">
            <h3 className="text-title-md font-bold text-primary mb-md flex items-center gap-xs">
              <span className="material-symbols-outlined text-secondary">calendar_today</span>
              {t('upcomingAppts')}
            </h3>
            
            {dashboardData?.upcoming_appointments?.length === 0 ? (
              <div className="p-xl border border-dashed border-outline-variant rounded-xl text-center text-outline">
                <span className="material-symbols-outlined text-4xl mb-sm">event_busy</span>
                <p className="text-sm font-semibold">{t('noAppts')}</p>
                <button 
                  onClick={() => navigate('/appointments')} 
                  className="text-secondary font-bold text-xs hover:underline mt-xs"
                >
                  {t('findDocToBook')}
                </button>
              </div>
            ) : (
              <div className="space-y-md">
                {dashboardData?.upcoming_appointments?.map((appt) => (
                  <div key={appt.id} className="p-md border border-outline-variant/50 rounded-xl bg-surface-container-lowest flex flex-col md:flex-row justify-between items-start md:items-center gap-md hover:border-secondary transition-all">
                    <div>
                      <h4 className="font-bold text-on-surface">{appt.doctor?.name || 'Doctor'}</h4>
                      <p className="text-xs text-outline font-semibold mb-xs">{appt.doctor?.specialization || 'Specialist'}</p>
                      <div className="flex gap-md text-xs text-on-surface-variant font-medium">
                        <span className="flex items-center gap-xs">
                          <span className="material-symbols-outlined text-[16px] text-secondary">calendar_month</span>
                          {appt.date}
                        </span>
                        <span className="flex items-center gap-xs">
                          <span className="material-symbols-outlined text-[16px] text-secondary">schedule</span>
                          {appt.time}
                        </span>
                      </div>
                    </div>
                    
                    <div className="flex gap-sm w-full md:w-auto">
                      <button 
                        onClick={() => handleCancelAppointment(appt.id)}
                        className="flex-1 md:flex-initial px-3 py-1.5 border border-error/30 hover:bg-error/5 text-error text-xs font-bold rounded-lg transition-colors active:scale-[0.98]"
                      >
                        {t('cancel')}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* AI Tip / Clinical Intelligence */}
          <div className="bg-gradient-to-r from-primary to-primary-container text-white rounded-2xl p-lg shadow-md relative overflow-hidden interactive-card">
            <div className="absolute right-0 bottom-0 opacity-10 pointer-events-none transform translate-y-1/4 translate-x-1/4">
              <span className="material-symbols-outlined text-[200px]">lightbulb</span>
            </div>
            <div className="relative z-10 space-y-md">
              <span className="px-2.5 py-1 bg-white/20 rounded-full text-[10px] font-bold tracking-wider uppercase">AI Daily Wellness Tip</span>
              <p className="font-body-lg text-lg leading-relaxed font-medium">
                "{dashboardData?.health_tip}"
              </p>
              <div className="flex items-center gap-xs text-xs opacity-75">
                <span className="material-symbols-outlined text-[16px]">info</span>
                <span>Powered by HealthAI Wellness Intelligence System</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Side: Activity Log & Quick Operations */}
        <div className="space-y-lg">
          {/* User Activity Logs */}
          <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg flex flex-col h-full interactive-card">
            <h3 className="text-title-md font-bold text-primary mb-md flex items-center gap-xs">
              <span className="material-symbols-outlined text-secondary">history</span>
              Recent Activity
            </h3>
            
            <div className="flex-1 space-y-md overflow-y-auto max-h-[360px]">
              {dashboardData?.activity_logs?.map((log, index) => (
                <div key={log.id || index} className="flex gap-md items-center justify-between border-b border-outline-variant/10 pb-3 last:border-0">
                  <div className="flex gap-md items-start min-w-0">
                    <div className="w-8 h-8 rounded-full bg-secondary-container text-on-secondary-container flex items-center justify-center shrink-0">
                      <span className="material-symbols-outlined text-[16px]">
                        {log.action === "Appointment Booked" ? "calendar_today" : "info"}
                      </span>
                    </div>
                    <div className="min-w-0">
                      <h4 className="font-bold text-on-surface text-sm truncate">{log.action}</h4>
                      <p className="text-xs text-on-surface-variant mb-0.5 break-words">{log.details}</p>
                      <span className="text-[10px] text-outline">
                        {new Date(log.timestamp).toLocaleString()}
                      </span>
                    </div>
                  </div>
                  {log.action === "Appointment Booked" && (
                    <button
                      onClick={() => handleCancelAppointment(log.id)}
                      className="p-1 hover:bg-error/10 text-error rounded-lg transition-all focus:outline-none shrink-0"
                      title={t('cancel') || "Cancel Appointment"}
                    >
                      <span className="material-symbols-outlined text-[18px]">cancel</span>
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
