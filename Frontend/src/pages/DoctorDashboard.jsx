import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function DoctorDashboard() {
  const { user } = useAuth();
  const [dashboardData, setDashboardData] = useState(null);
  const [activeSOS, setActiveSOS] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadData = async () => {
    try {
      const data = await api.getDoctorDashboard();
      setDashboardData(data);
      
      // Load active emergencies
      const alerts = await api.getEmergencyAlerts();
      setActiveSOS(alerts);
    } catch (err) {
      console.error(err);
      setError("Failed to load doctor workspace details.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000); // Poll every 15s for new SOS alerts
    return () => clearInterval(interval);
  }, []);

  const handleResolveSOS = async (alertId) => {
    try {
      await api.resolveEmergencyAlert(alertId);
      setActiveSOS(prev => prev.filter(item => item.id !== alertId));
      loadData();
    } catch (err) {
      alert("Failed to resolve alert: " + err.message);
    }
  };

  if (loading) {
    return (
      <div className="space-y-xl animate-pulse">
        <div className="h-12 bg-surface-container rounded-xl w-1/3"></div>
        <div className="h-24 bg-error-container/20 rounded-xl"></div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
          <div className="lg:col-span-2 space-y-md">
            <div className="h-64 bg-surface-container rounded-xl"></div>
          </div>
          <div className="h-96 bg-surface-container rounded-xl"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-xl animate-in fade-in duration-300">
      <header>
        <h2 className="text-on-surface font-headline-lg text-headline-lg">
          Clinician Workspace
        </h2>
        <p className="text-on-surface-variant font-body-md text-body-md">Manage active patient emergencies, upcoming consultations, and clinical records.</p>
      </header>

      {error && (
        <div className="p-4 bg-error-container text-on-error-container rounded-xl flex items-center gap-sm">
          <span className="material-symbols-outlined">error</span>
          <p>{error}</p>
        </div>
      )}

      {/* EMERGENCY SOS ALERTS PANELS */}
      {activeSOS.length > 0 && (
        <section className="bg-error-container/20 border border-error/20 p-lg rounded-2xl space-y-md animate-bounce-short">
          <div className="flex items-center gap-sm text-error">
            <span className="material-symbols-outlined text-4xl animate-pulse">emergency</span>
            <div>
              <h3 className="font-bold text-lg">CRITICAL EMERGENCY SOS ACTIVE</h3>
              <p className="text-xs opacity-90">Patients require immediate medical attention. Address is broadcasted below.</p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
            {activeSOS.map(alert => (
              <div key={alert.id} className="p-md bg-white border border-error/30 rounded-xl shadow-sm flex flex-col justify-between interactive-card">
                <div className="space-y-xs">
                  <div className="flex justify-between items-start">
                    <span className="text-sm font-bold text-primary">{alert.patient_name}</span>
                    <span className="px-2 py-0.5 bg-error text-on-error text-[10px] rounded font-bold uppercase">Active SOS</span>
                  </div>
                  <p className="text-xs text-on-surface font-medium flex items-center gap-xs">
                    <span className="material-symbols-outlined text-[16px] text-error">home_pin</span>
                    Address: {alert.patient_address}
                  </p>
                  <p className="text-[10px] text-outline">
                    Triggered at: {new Date(alert.created_at).toLocaleTimeString()}
                  </p>
                </div>
                <button
                  onClick={() => handleResolveSOS(alert.id)}
                  className="mt-md w-full bg-error text-on-error py-2 rounded-lg font-bold text-xs hover:bg-error/95 transition-colors"
                >
                  Mark Alert Resolved
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Main Stats Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-md">
        <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg interactive-card">
          <div className="flex items-center gap-md">
            <div className="w-12 h-12 rounded-xl bg-primary-fixed text-primary flex items-center justify-center">
              <span className="material-symbols-outlined text-[28px]">group</span>
            </div>
            <div>
              <span className="text-xs text-outline font-semibold uppercase block">Total Patients</span>
              <span className="text-2xl font-bold text-primary">{dashboardData?.total_patients}</span>
            </div>
          </div>
        </div>

        <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg interactive-card">
          <div className="flex items-center gap-md">
            <div className="w-12 h-12 rounded-xl bg-secondary-fixed text-on-secondary-container flex items-center justify-center">
              <span className="material-symbols-outlined text-[28px]">today</span>
            </div>
            <div>
              <span className="text-xs text-outline font-semibold uppercase block">Today's Visits</span>
              <span className="text-2xl font-bold text-primary">{dashboardData?.today_appointments?.length}</span>
            </div>
          </div>
        </div>

        <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg interactive-card">
          <div className="flex items-center gap-md">
            <div className="w-12 h-12 rounded-xl bg-tertiary-fixed text-on-tertiary-fixed flex items-center justify-center">
              <span className="material-symbols-outlined text-[28px]">pending_actions</span>
            </div>
            <div>
              <span className="text-xs text-outline font-semibold uppercase block">Pending Consults</span>
              <span className="text-2xl font-bold text-primary">{dashboardData?.pending_appointments}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
        {/* Appointments List */}
        <div className="lg:col-span-2 space-y-lg">
          <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg interactive-card">
            <h3 className="text-title-md font-bold text-primary mb-md flex items-center gap-xs">
              <span className="material-symbols-outlined text-secondary font-bold">calendar_month</span>
              Upcoming Consultations
            </h3>

            {dashboardData?.upcoming_appointments?.length === 0 ? (
              <div className="p-xl border border-dashed border-outline-variant rounded-xl text-center text-outline">
                <p className="text-sm font-semibold">No upcoming patient visits scheduled.</p>
              </div>
            ) : (
              <div className="space-y-md">
                {dashboardData?.upcoming_appointments?.map(appt => (
                  <div key={appt.id} className="p-md border border-outline-variant/50 rounded-xl bg-surface-container-lowest flex flex-col md:flex-row justify-between items-start md:items-center gap-md">
                    <div>
                      <h4 className="font-bold text-on-surface">Patient: {appt.patient_email}</h4>
                      <div className="flex gap-md text-xs text-on-surface-variant font-medium mt-sm">
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
                    <span className="px-3 py-1 bg-secondary-container text-on-secondary-container text-xs font-bold rounded-full capitalize">
                      {appt.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Patients Summary Directory */}
        <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg flex flex-col h-full">
          <h3 className="text-title-md font-bold text-primary mb-md flex items-center gap-xs">
            <span className="material-symbols-outlined text-secondary">group</span>
            Patients Directory
          </h3>

          <div className="flex-1 space-y-md overflow-y-auto max-h-[400px]">
            {dashboardData?.patient_summaries?.map(p => (
              <div key={p.user_id} className="p-md border border-outline-variant/30 rounded-xl hover:border-secondary transition-colors">
                <h4 className="font-bold text-on-surface text-sm">{p.name}</h4>
                <p className="text-xs text-on-surface-variant mt-xs">
                  Gender: {p.gender || 'Not specified'} | Age: {p.age || 'Not specified'}
                </p>
                <p className="text-xs text-outline font-semibold">User ID: {p.user_id}</p>
              </div>
            ))}
            {dashboardData?.patient_summaries?.length === 0 && (
              <p className="text-center text-xs text-outline py-xl">No patients registered in the directory.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
