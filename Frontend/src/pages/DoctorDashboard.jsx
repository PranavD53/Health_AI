import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { useWebSocket } from '../context/WebSocketContext';

export default function DoctorDashboard() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [dashboardData, setDashboardData] = useState(null);
  const [activeSOS, setActiveSOS] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [reminders, setReminders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Interactivity state & refs
  const [filterType, setFilterType] = useState('all'); // 'all', 'today', 'pending'
  const patientsSectionRef = useRef(null);
  const feedbackSectionRef = useRef(null);

  const scrollToSection = (ref) => {
    ref.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handlePatientClick = (patientUserId) => {
    navigate('/chat', { state: { selectUserId: patientUserId } });
  };

  const getFilteredAppointments = () => {
    if (!dashboardData || !dashboardData.upcoming_appointments) return [];
    if (filterType === 'today') {
      const todayStr = new Date().toISOString().slice(0, 10);
      const todayLocaleStr = new Date().toLocaleDateString();
      return dashboardData.upcoming_appointments.filter(appt => {
        return appt.date.includes(todayStr) || todayStr.includes(appt.date) || appt.date.includes(todayLocaleStr) || todayLocaleStr.includes(appt.date);
      });
    }
    if (filterType === 'pending') {
      return dashboardData.upcoming_appointments.filter(appt => appt.status === 'booked' || appt.status === 'pending');
    }
    return dashboardData.upcoming_appointments;
  };

  const loadData = async () => {
    try {
      const data = await api.getDoctorDashboard();
      setDashboardData(data);
      
      // Load active emergencies
      const alerts = await api.getEmergencyAlerts();
      setActiveSOS(alerts);

      // Load feedback analytics
      const docId = user?.doctor_profile_id || data?.id;
      if (docId) {
        try {
          const docAnalytics = await api.getDoctorFeedbackAnalytics(docId);
          setAnalytics(docAnalytics);
          const docReviews = await api.getDoctorFeedbacks(docId);
          setReviews(docReviews);
        } catch (e) {
          console.error("Failed to load feedback analytics: ", e);
        }
      }
    } catch (err) {
      console.error(err);
      setError("Failed to load doctor workspace details.");
    } finally {
      setLoading(false);
    }
  };

  const loadReminders = async () => {
    try {
      const data = await api.getReminders();
      setReminders(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("Failed to load reminders: ", e);
    }
  };

  const handleCompleteAppointment = async (apptId) => {
    if (window.confirm("Are you sure you want to mark this consultation as completed?")) {
      try {
        await api.completeAppointment(apptId);
        loadData();
      } catch (err) {
        alert("Failed to complete appointment: " + err.message);
      }
    }
  };

  const { subscribe } = useWebSocket() || {};

  useEffect(() => {
    loadData();
    loadReminders();
  }, []);

  useEffect(() => {
    const handleRemindersUpdated = () => {
      loadReminders();
    };
    window.addEventListener('reminders_updated', handleRemindersUpdated);
    return () => {
      window.removeEventListener('reminders_updated', handleRemindersUpdated);
    };
  }, []);

  useEffect(() => {
    if (!subscribe) return;
    const unsubscribe = subscribe((data) => {
      if (data.event === 'new_alert') {
        loadData();
      }
    });
    return unsubscribe;
  }, [subscribe]);

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
          {t('workspace')}
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
                  {alert.latitude !== null && alert.longitude !== null && alert.latitude !== undefined && alert.longitude !== undefined && (
                    <div className="mt-xs mb-xs space-y-xs">
                      <p className="text-xs text-on-surface font-medium flex items-center gap-xs">
                        <span className="material-symbols-outlined text-[16px] text-primary">location_on</span>
                        GPS: {Number(alert.latitude).toFixed(6)}, {Number(alert.longitude).toFixed(6)}
                      </p>
                      <a 
                        href={`https://www.google.com/maps/search/?api=1&query=${alert.latitude},${alert.longitude}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-primary hover:underline font-bold flex items-center gap-xs"
                      >
                        <span className="material-symbols-outlined text-[16px]">map</span>
                        Navigate on Google Maps
                      </a>
                    </div>
                  )}
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
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-md">
        <div 
          onClick={() => scrollToSection(patientsSectionRef)}
          className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg interactive-card cursor-pointer hover:shadow-md hover:border-primary/50 transition-all active:scale-[0.98]"
          title="Scroll to Patients Directory"
        >
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

        <div 
          onClick={() => setFilterType(filterType === 'today' ? 'all' : 'today')}
          className={`bg-white border rounded-2xl shadow-sm p-lg interactive-card cursor-pointer hover:shadow-md transition-all active:scale-[0.98] ${
            filterType === 'today' ? 'border-primary ring-2 ring-primary/20 bg-primary-container/5' : 'border-outline-variant/30'
          }`}
          title="Filter by Today's Visits"
        >
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

        <div 
          onClick={() => setFilterType(filterType === 'pending' ? 'all' : 'pending')}
          className={`bg-white border rounded-2xl shadow-sm p-lg interactive-card cursor-pointer hover:shadow-md transition-all active:scale-[0.98] ${
            filterType === 'pending' ? 'border-primary ring-2 ring-primary/20 bg-primary-container/5' : 'border-outline-variant/30'
          }`}
          title="Filter by Pending Consultations"
        >
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

        <div 
          onClick={() => scrollToSection(feedbackSectionRef)}
          className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg interactive-card cursor-pointer hover:shadow-md hover:border-primary/50 transition-all active:scale-[0.98]"
          title="Scroll to Reviews & Feedback Analytics"
        >
          <div className="flex items-center gap-md">
            <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
              <span className="material-symbols-outlined text-[28px]" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
            </div>
            <div>
              <span className="text-xs text-outline font-semibold uppercase block">Average Rating</span>
              <div className="flex items-baseline gap-xs">
                <span className="text-2xl font-bold text-primary">
                  {analytics ? analytics.average_doctor : (dashboardData?.rating || 4.9)}
                </span>
                <span className="text-[10px] text-outline font-bold">({reviews.length} reviews)</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
        {/* Appointments List */}
        <div className="lg:col-span-2 space-y-lg">
          <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg interactive-card">
            <h3 className="text-title-md font-bold text-primary mb-md flex flex-col sm:flex-row sm:items-center justify-between gap-sm">
              <span className="flex items-center gap-xs">
                <span className="material-symbols-outlined text-secondary font-bold">calendar_month</span>
                Upcoming Consultations
                {filterType !== 'all' && (
                  <span className="text-[10px] bg-secondary-container text-on-secondary-container px-2 py-0.5 rounded font-bold capitalize">
                    Filtered: {filterType}
                  </span>
                )}
              </span>
              <div className="flex items-center gap-sm">
                <button
                  onClick={async () => {
                    const docId = dashboardData?.id;
                    if (!docId) {
                      alert("Error loading doctor profile ID.");
                      return;
                    }
                    if (window.confirm("URGENT: Are you performing an urgent surgery? This will automatically reassign all your upcoming booked appointments to other available specialists in your department.")) {
                      try {
                        const result = await api.triggerSurgeryReplacement(docId);
                        alert(`Reassignment process finished successfully! Reassigned appointments: ${result.reassigned_count || 0}.`);
                        loadData();
                      } catch (err) {
                        alert("Reassignment failed: " + err.message);
                      }
                    }
                  }}
                  className="flex items-center gap-xs bg-error hover:bg-error/95 text-on-error text-[10px] font-bold px-3 py-1.5 rounded-lg shadow transition active:scale-95 focus:outline-none"
                  title="Single one-stop button to reassign all your visits due to urgent surgery"
                >
                  <span className="material-symbols-outlined text-[14px]">medical_services</span>
                  Urgent Surgery: Reassign
                </button>
                {filterType !== 'all' && (
                  <button 
                    onClick={() => setFilterType('all')} 
                    className="text-[10px] text-primary hover:underline font-bold flex items-center gap-2xs focus:outline-none"
                  >
                    Clear Filter
                  </button>
                )}
              </div>
            </h3>

            {getFilteredAppointments().length === 0 ? (
              <div className="p-xl border border-dashed border-outline-variant rounded-xl text-center text-outline">
                <p className="text-sm font-semibold">
                  {filterType === 'all' 
                    ? "No upcoming patient visits scheduled." 
                    : `No upcoming visits matching filter: ${filterType}`}
                </p>
              </div>
            ) : (
              <div className="space-y-md">
                {getFilteredAppointments().map(appt => (
                  <div key={appt.id} className="p-md border border-outline-variant/50 rounded-xl bg-surface-container-lowest flex flex-col md:flex-row justify-between items-start md:items-center gap-md">
                    <div>
                      <h4 className="font-bold text-on-surface flex items-center gap-sm">
                        Patient: {appt.patient_name}
                        <span className={`px-2.5 py-0.5 rounded text-[9px] font-bold uppercase border ${
                          appt.priority === 'High' 
                            ? 'bg-error-container text-on-error-container border-error/20' 
                            : appt.priority === 'Low' 
                            ? 'bg-surface-container-high text-outline border-outline-variant/30' 
                            : 'bg-secondary-container text-on-secondary-container border-secondary/20'
                        }`}>
                          {appt.priority || 'Normal'}
                        </span>
                      </h4>
                      <div className="flex flex-wrap gap-md text-xs text-on-surface-variant font-medium mt-sm items-center">
                        <span className="flex items-center gap-xs">
                          <span className="material-symbols-outlined text-[16px] text-secondary">calendar_month</span>
                          {appt.date}
                        </span>
                        <span className="flex items-center gap-xs">
                          <span className="material-symbols-outlined text-[16px] text-secondary">schedule</span>
                          {appt.time}
                        </span>
                        <div className="flex items-center gap-xs ml-sm">
                          <span className="text-[10px] text-outline">Priority:</span>
                          <select
                            value={appt.priority || 'Normal'}
                            onChange={async (e) => {
                              try {
                                await api.updateAppointmentPriority(appt.id, e.target.value);
                                loadData();
                              } catch (err) {
                                alert("Failed to update risk level: " + err.message);
                              }
                            }}
                            className="text-[10px] border border-outline-variant rounded bg-surface py-0.5 px-1 font-bold text-on-surface focus:outline-none cursor-pointer"
                          >
                            <option value="High">High</option>
                            <option value="Normal">Normal</option>
                            <option value="Low">Low</option>
                          </select>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-sm">
                      <span className="px-3 py-1 bg-secondary-container text-on-secondary-container text-xs font-bold rounded-full capitalize">
                        {appt.status}
                      </span>
                      {appt.status === 'booked' && (
                        <button
                          onClick={() => handleCompleteAppointment(appt.id)}
                          className="px-3 py-1.5 bg-secondary hover:bg-secondary/95 text-white text-xs font-bold rounded-lg transition-colors active:scale-[0.98]"
                        >
                          {t('completeVisit') || 'Complete Visit'}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Sidebar: Patients Directory & Leave Request Submissions */}
        <div className="space-y-lg">
          {/* Patients Summary Directory */}
          <div ref={patientsSectionRef} className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg flex flex-col interactive-card">
            <h3 className="text-title-md font-bold text-primary mb-md flex items-center gap-xs">
              <span className="material-symbols-outlined text-secondary">group</span>
              Patients Directory
            </h3>

            <div className="space-y-md overflow-y-auto max-h-[300px]">
              {dashboardData?.patient_summaries?.map(p => (
                <div 
                  key={p.user_id} 
                  onClick={() => handlePatientClick(p.user_id)}
                  className="p-md border border-outline-variant/30 rounded-xl hover:border-secondary cursor-pointer hover:bg-surface-container-high/40 active:scale-[0.99] transition-all"
                  title={`Chat with ${p.name}`}
                >
                  <h4 className="font-bold text-on-surface text-sm">{p.name}</h4>
                  <p className="text-xs text-on-surface-variant mt-xs">
                    Gender: {p.gender || 'Not specified'} | Age: {p.age || 'Not specified'}
                  </p>
                </div>
              ))}
              {dashboardData?.patient_summaries?.length === 0 && (
                <p className="text-center text-xs text-outline py-xl">No patients registered in the directory.</p>
              )}
            </div>
          </div>

          {/* Consultation Reminders Card */}
          <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg interactive-card space-y-md">
            <h3 className="text-title-md font-bold text-primary flex items-center gap-xs border-b border-outline-variant/20 pb-2">
              <span className="material-symbols-outlined text-secondary">notifications_active</span>
              Consultation Reminders
            </h3>
            <form onSubmit={async (e) => {
              e.preventDefault();
              const medicine_name = e.target.medicine_name.value;
              const dosage = e.target.dosage.value;
              const time = e.target.time.value;
              const method = e.target.method.value;
              const contact_info = e.target.contact_info.value;
              try {
                await api.createReminder({
                  medicine_name,
                  dosage,
                  time,
                  method,
                  contact_info,
                  days: "Daily"
                });
                alert("Consultation reminder successfully set!");
                e.target.reset();
                loadReminders();
              } catch (err) {
                alert("Failed to create reminder: " + err.message);
              }
            }} className="space-y-sm text-xs">
              <div className="space-y-xs">
                <label className="font-bold text-outline uppercase block">Consultation / Patient Name</label>
                <input required type="text" name="medicine_name" placeholder="e.g. Patient: John Doe" className="w-full border border-outline-variant rounded p-2 bg-surface text-on-surface focus:border-primary outline-none" />
              </div>
              <div className="grid grid-cols-2 gap-sm">
                <div className="space-y-xs">
                  <label className="font-bold text-outline uppercase block">Preparation / Notes</label>
                  <input required type="text" name="dosage" placeholder="e.g. Review heart logs" className="w-full border border-outline-variant rounded p-2 bg-surface text-on-surface focus:border-primary outline-none" />
                </div>
                <div className="space-y-xs">
                  <label className="font-bold text-outline uppercase block">Time</label>
                  <input required type="time" name="time" className="w-full border border-outline-variant rounded p-2 bg-surface text-on-surface focus:border-primary outline-none" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-sm">
                <div className="space-y-xs">
                  <label className="font-bold text-outline uppercase block">Notify Via</label>
                  <select name="method" defaultValue="app" className="w-full border border-outline-variant rounded p-2 bg-surface text-on-surface focus:border-primary outline-none font-bold">
                    <option value="app">In-App Notification</option>
                    <option value="email">Email Alert</option>
                    <option value="sms">SMS Alert</option>
                  </select>
                </div>
                <div className="space-y-xs">
                  <label className="font-bold text-outline uppercase block">Contact Info (Optional)</label>
                  <input type="text" name="contact_info" placeholder="Email / Mobile" className="w-full border border-outline-variant rounded p-2 bg-surface text-on-surface focus:border-primary outline-none" />
                </div>
              </div>
              <button type="submit" className="w-full bg-primary hover:bg-primary/95 text-white py-2 rounded font-bold shadow-md transition active:scale-[0.98]">
                Add Reminder
              </button>
            </form>

            {/* Reminders List */}
            {reminders.length === 0 ? (
              <p className="text-center text-xs text-outline py-2">No consultation reminders configured.</p>
            ) : (
              <div className="pt-2 border-t border-outline-variant/30 space-y-2">
                <span className="text-[10px] text-outline font-bold uppercase tracking-wider block">Your Schedule Log</span>
                <div className="space-y-2 max-h-[180px] overflow-y-auto pr-xs">
                  {reminders.map(rem => (
                    <div key={rem.id} className={`p-2 border rounded-xl bg-surface-container-low flex justify-between items-center transition-all ${
                      rem.is_active ? 'border-outline-variant/40' : 'border-outline-variant/10 opacity-60'
                    }`}>
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-xs">
                          <span className={`material-symbols-outlined text-[14px] ${rem.is_active ? 'text-secondary' : 'text-outline'}`}>
                            {rem.method === 'email' ? 'mail' : rem.method === 'sms' ? 'sms' : 'notifications'}
                          </span>
                          <span className={`font-bold text-xs ${rem.is_active ? 'text-on-surface' : 'text-outline line-through'}`}>
                            {rem.medicine_name}
                          </span>
                        </div>
                        <p className="text-[9px] text-on-surface-variant">
                          Notes: {rem.dosage} | Time: {rem.time}
                        </p>
                      </div>
                      
                      <div className="flex items-center gap-sm">
                        <button
                          type="button"
                          onClick={async () => {
                            try {
                              await api.toggleReminder(rem.id);
                              loadReminders();
                            } catch (err) {
                              alert("Failed to toggle status: " + err.message);
                            }
                          }}
                          className={`p-1 rounded-lg transition-colors focus:outline-none ${
                            rem.is_active ? 'text-success hover:bg-success/10' : 'text-outline hover:bg-outline-variant/10'
                          }`}
                          title={rem.is_active ? "Pause Reminder" : "Resume Reminder"}
                        >
                          <span className="material-symbols-outlined text-[16px]">
                            {rem.is_active ? 'pause' : 'play_arrow'}
                          </span>
                        </button>
                        
                        <button
                          type="button"
                          onClick={async () => {
                            if (window.confirm("Delete this reminder?")) {
                              try {
                                await api.deleteReminder(rem.id);
                                loadReminders();
                              } catch (err) {
                                alert("Failed to delete: " + err.message);
                              }
                            }
                          }}
                          className="p-1 text-outline hover:text-error hover:bg-error/10 rounded-lg transition-colors focus:outline-none"
                          title="Delete Reminder"
                        >
                          <span className="material-symbols-outlined text-[16px]">delete</span>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Leave Request Card */}
          <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg interactive-card space-y-md">
            <h3 className="text-title-md font-bold text-primary flex items-center gap-xs border-b border-outline-variant/20 pb-2">
              <span className="material-symbols-outlined text-secondary">calendar_today</span>
              Submit Leave Request
            </h3>
            <form onSubmit={async (e) => {
              e.preventDefault();
              const start = e.target.start_date.value;
              const end = e.target.end_date.value;
              const reason = e.target.reason.value;
              try {
                await api.requestLeave({ start_date: start, end_date: end, reason });
                alert("Leave request submitted successfully for administrator approval!");
                e.target.reset();
                loadData();
              } catch (err) {
                alert("Failed to submit leave request: " + err.message);
              }
            }} className="space-y-sm text-xs">
              <div className="grid grid-cols-2 gap-sm">
                <div className="space-y-xs">
                  <label className="font-bold text-outline uppercase block">Start Date</label>
                  <input required type="date" name="start_date" className="w-full border border-outline-variant rounded p-2 bg-surface text-on-surface focus:border-primary outline-none" />
                </div>
                <div className="space-y-xs">
                  <label className="font-bold text-outline uppercase block">End Date</label>
                  <input required type="date" name="end_date" className="w-full border border-outline-variant rounded p-2 bg-surface text-on-surface focus:border-primary outline-none" />
                </div>
              </div>
              <div className="space-y-xs">
                <label className="font-bold text-outline uppercase block">Reason</label>
                <textarea required name="reason" rows="2" placeholder="e.g. Attending conference, urgent medical leave" className="w-full border border-outline-variant rounded p-2 bg-surface text-on-surface focus:border-primary outline-none" />
              </div>
              <button type="submit" className="w-full bg-primary hover:bg-primary/95 text-white py-2 rounded font-bold shadow-md transition active:scale-[0.98]">
                Submit Request
              </button>
            </form>

            {/* Leave requests logs */}
            {dashboardData?.leave_requests && dashboardData.leave_requests.length > 0 && (
              <div className="pt-2 border-t border-outline-variant/30 space-y-xs">
                <span className="text-[10px] text-outline font-bold uppercase tracking-wider block">Leave Requests Log</span>
                <div className="space-y-2 max-h-[150px] overflow-y-auto pr-xs">
                  {dashboardData.leave_requests.map(req => (
                    <div key={req.id} className="p-2 border border-outline-variant/20 rounded bg-surface-container-low flex justify-between items-center text-[10px]">
                      <div>
                        <span className="font-bold text-on-surface">{req.start_date} to {req.end_date}</span>
                        <p className="text-outline italic truncate max-w-[130px]">{req.reason}</p>
                      </div>
                      <span className={`px-2 py-0.5 rounded font-bold uppercase text-[8px] ${
                        req.status === 'approved' 
                          ? 'bg-emerald-100 text-emerald-800' 
                          : req.status === 'rejected' 
                          ? 'bg-error-container text-on-error-container' 
                          : 'bg-surface-container text-outline'
                      }`}>
                        {req.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Feedback Analytics & Patient Reviews */}
      <section ref={feedbackSectionRef} className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg interactive-card space-y-lg">
        <h3 className="text-title-md font-bold text-primary mb-md flex items-center gap-xs border-b border-outline-variant/20 pb-xs">
          <span className="material-symbols-outlined text-secondary">analytics</span>
          {t('feedbackAnalytics') || 'Feedback Analytics & Reviews'}
        </h3>

        {/* Categories Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-md">
          <div className="p-md bg-surface-container-lowest rounded-xl border border-outline-variant/20 text-center space-y-1">
            <span className="text-[10px] text-outline font-bold uppercase tracking-wider block">{t('ratingCommunication') || 'Communication'}</span>
            <div className="text-lg font-bold text-primary flex items-center justify-center gap-xs">
              {analytics?.average_communication || 0} / 5
              <span className="material-symbols-outlined text-[16px] text-amber-500" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
            </div>
          </div>

          <div className="p-md bg-surface-container-lowest rounded-xl border border-outline-variant/20 text-center space-y-1">
            <span className="text-[10px] text-outline font-bold uppercase tracking-wider block">{t('ratingProfessionalism') || 'Professionalism'}</span>
            <div className="text-lg font-bold text-primary flex items-center justify-center gap-xs">
              {analytics?.average_professionalism || 0} / 5
              <span className="material-symbols-outlined text-[16px] text-amber-500" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
            </div>
          </div>

          <div className="p-md bg-surface-container-lowest rounded-xl border border-outline-variant/20 text-center space-y-1">
            <span className="text-[10px] text-outline font-bold uppercase tracking-wider block">{t('ratingWaitTime') || 'Wait Time'}</span>
            <div className="text-lg font-bold text-primary flex items-center justify-center gap-xs">
              {analytics?.average_wait_time || 0} / 5
              <span className="material-symbols-outlined text-[16px] text-amber-500" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
            </div>
          </div>

          <div className="p-md bg-surface-container-lowest rounded-xl border border-outline-variant/20 text-center space-y-1">
            <span className="text-[10px] text-outline font-bold uppercase tracking-wider block">{t('ratingSatisfaction') || 'Satisfaction'}</span>
            <div className="text-lg font-bold text-primary flex items-center justify-center gap-xs">
              {analytics?.average_satisfaction || 0} / 5
              <span className="material-symbols-outlined text-[16px] text-amber-500" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
            </div>
          </div>
        </div>

        {/* Written Review Comments */}
        <div className="space-y-md">
          <h4 className="font-bold text-on-surface text-sm">Patient Reviews Checklist</h4>
          
          {reviews.length === 0 ? (
            <p className="text-center text-xs text-outline py-md">{t('noReviewsMsg') || 'No reviews submitted yet.'}</p>
          ) : (
            <div className="space-y-md max-h-[350px] overflow-y-auto pr-xs">
              {reviews.map(review => (
                <div key={review.id} className="p-md border border-outline-variant/30 rounded-xl bg-surface-container-lowest space-y-sm">
                  <div className="flex justify-between items-start">
                    <div className="flex items-center gap-xs">
                      {/* Overall stars */}
                      <div className="flex gap-0.5">
                        {[1, 2, 3, 4, 5].map(star => (
                          <span 
                            key={star} 
                            className={`material-symbols-outlined text-[16px] ${star <= review.rating_doctor ? 'text-amber-500' : 'text-outline-variant/30'}`}
                            style={{ fontVariationSettings: star <= review.rating_doctor ? "'FILL' 1" : "'FILL' 0" }}
                          >
                            star
                          </span>
                        ))}
                      </div>
                      <span className="text-[10px] bg-secondary-container text-on-secondary-container font-bold px-2 py-0.5 rounded">
                        Overall: {review.rating_overall}/5
                      </span>
                      {!review.is_approved && (
                        <span className="text-[9px] bg-error-container text-on-error-container font-bold px-2 py-0.5 rounded uppercase">
                          Pending Moderation
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] text-outline">
                      {new Date(review.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  
                  {review.comments && (
                    <p className="text-xs text-on-surface font-medium italic">
                      "{review.comments}"
                    </p>
                  )}
                  
                  <div className="flex justify-between items-center text-[10px] text-outline font-semibold">
                    <span>{t('anonymousReview') || 'Verified Patient'}</span>
                    <div className="flex gap-md">
                      {review.rating_communication && <span>Comm: {review.rating_communication}</span>}
                      {review.rating_professionalism && <span>Ethics: {review.rating_professionalism}</span>}
                      {review.rating_wait_time && <span>Wait: {review.rating_wait_time}</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
