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
  const [appointments, setAppointments] = useState([]);
  const [pendingFeedbacks, setPendingFeedbacks] = useState([]);
  const [currentFeedbackAppt, setCurrentFeedbackAppt] = useState(null);
  const [reminders, setReminders] = useState([]);
  
  // Feedback form states
  const [ratingOverall, setRatingOverall] = useState(0);
  const [ratingDoctor, setRatingDoctor] = useState(0);
  const [comments, setComments] = useState('');
  const [ratingComm, setRatingComm] = useState(0);
  const [ratingProf, setRatingProf] = useState(0);
  const [ratingWait, setRatingWait] = useState(0);
  const [ratingSat, setRatingSat] = useState(0);
  
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackSuccess, setFeedbackSuccess] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  
  // Custom Interaction States
  const [showTipModal, setShowTipModal] = useState(false);
  const [refreshTipLoading, setRefreshTipLoading] = useState(false);
  const [selectedActivity, setSelectedActivity] = useState(null);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadDashboard = async () => {
    try {
      const data = await api.getPatientDashboard(currentLanguage);
      setDashboardData(data);
      
      const appts = await api.getMyAppointments();
      setAppointments(appts);
      
      const pending = await api.getPendingFeedbacks();
      setPendingFeedbacks(pending);
      if (pending && pending.length > 0) {
        const firstPending = pending[0];
        // Format it so doctor details are mapped properly
        setCurrentFeedbackAppt({
          id: firstPending.id,
          doctor_id: firstPending.doctor_id,
          doctor: {
            name: firstPending.doctor_name,
            specialization: firstPending.specialization
          },
          date: firstPending.date,
          time: firstPending.time
        });
        setIsEditMode(false);
      }
    } catch (err) {
      console.error(err);
      setError("Failed to load dashboard data.");
    } finally {
      setLoading(false);
    }
  };

  const loadReminders = async () => {
    try {
      const data = await api.getReminders();
      setReminders(data);
    } catch (e) {
      console.error("Failed to load reminders: ", e);
    }
  };

  const handleRefreshTip = async () => {
    setRefreshTipLoading(true);
    try {
      const data = await api.getPatientDashboard(currentLanguage);
      setDashboardData(prev => ({
        ...prev,
        health_tip: data.health_tip
      }));
    } catch (e) {
      console.error(e);
    } finally {
      setRefreshTipLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
    loadReminders();
  }, [currentLanguage]);

  useEffect(() => {
    const handleRemindersUpdated = () => {
      loadReminders();
    };
    window.addEventListener('reminders_updated', handleRemindersUpdated);
    return () => {
      window.removeEventListener('reminders_updated', handleRemindersUpdated);
    };
  }, []);

  const handleOpenFeedback = async (appt) => {
    try {
      setFeedbackLoading(true);
      const existing = await api.getFeedbackForAppointment(appt.id);
      if (existing) {
        setRatingOverall(existing.rating_overall);
        setRatingDoctor(existing.rating_doctor);
        setComments(existing.comments || '');
        setRatingComm(existing.rating_communication || 0);
        setRatingProf(existing.rating_professionalism || 0);
        setRatingWait(existing.rating_wait_time || 0);
        setRatingSat(existing.rating_satisfaction || 0);
        setIsEditMode(true);
      } else {
        setRatingOverall(0);
        setRatingDoctor(0);
        setComments('');
        setRatingComm(0);
        setRatingProf(0);
        setRatingWait(0);
        setRatingSat(0);
        setIsEditMode(false);
      }
      setCurrentFeedbackAppt(appt);
    } catch (err) {
      alert("Failed to load feedback details: " + err.message);
    } finally {
      setFeedbackLoading(false);
    }
  };

  const handleConfirmFeedback = async (e) => {
    e.preventDefault();
    if (ratingOverall === 0 || ratingDoctor === 0) {
      alert(t('feedbackFormError'));
      return;
    }
    
    setFeedbackLoading(true);
    try {
      const payload = {
        appointment_id: currentFeedbackAppt.id,
        rating_overall: ratingOverall,
        rating_doctor: ratingDoctor,
        comments: comments || null,
        rating_communication: ratingComm || null,
        rating_professionalism: ratingProf || null,
        rating_wait_time: ratingWait || null,
        rating_satisfaction: ratingSat || null
      };
      
      await api.submitFeedback(payload, isEditMode);
      setFeedbackSuccess(true);
      
      setTimeout(() => {
        setCurrentFeedbackAppt(null);
        setFeedbackSuccess(false);
        loadDashboard();
      }, 1500);
    } catch (err) {
      alert("Failed to submit feedback: " + err.message);
    } finally {
      setFeedbackLoading(false);
    }
  };

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
                    <div 
                      onClick={() => appt.doctor?.user_id && navigate('/chat', { state: { selectUserId: appt.doctor.user_id } })}
                      className="cursor-pointer group flex-1"
                      title="Click to chat with this doctor"
                    >
                      <h4 className="font-bold text-on-surface group-hover:text-primary transition-colors flex items-center gap-xs">
                        {appt.doctor?.name || 'Doctor'}
                        <span className="material-symbols-outlined text-sm opacity-0 group-hover:opacity-100 transition-opacity">chat</span>
                      </h4>
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

          {/* Consultation History */}
          <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg interactive-card">
            <h3 className="text-title-md font-bold text-primary mb-md flex items-center gap-xs">
              <span className="material-symbols-outlined text-secondary">history_edu</span>
              Consultation History
            </h3>
            
            {appointments.filter(appt => appt.status === 'completed' || appt.status === 'cancelled').length === 0 ? (
              <div className="p-md text-center text-outline text-xs">
                No past consultations found.
              </div>
            ) : (
              <div className="space-y-md">
                {appointments.filter(appt => appt.status === 'completed' || appt.status === 'cancelled').map((appt) => {
                  const isPending = pendingFeedbacks.some(p => p.id === appt.id);
                  return (
                    <div key={appt.id} className="p-md border border-outline-variant/50 rounded-xl bg-surface-container-lowest flex flex-col md:flex-row justify-between items-start md:items-center gap-md hover:border-secondary transition-all">
                      <div
                        onClick={() => appt.doctor?.user_id && navigate('/chat', { state: { selectUserId: appt.doctor.user_id } })}
                        className="cursor-pointer group flex-1"
                        title="Click to chat with this doctor"
                      >
                        <h4 className="font-bold text-on-surface group-hover:text-primary transition-colors flex items-center gap-xs">
                          {appt.doctor?.name || 'Doctor'}
                          <span className="material-symbols-outlined text-sm opacity-0 group-hover:opacity-100 transition-opacity">chat</span>
                        </h4>
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
                      
                      <div className="flex items-center gap-md w-full md:w-auto justify-between md:justify-end">
                        <span className={`px-2.5 py-0.5 rounded text-[10px] font-bold ${
                          appt.status === 'completed' ? 'bg-success/15 text-success' : 'bg-outline/20 text-outline'
                        }`}>
                          {appt.status}
                        </span>
                        
                        {appt.status === 'completed' && (
                          <button
                            onClick={() => handleOpenFeedback(appt)}
                            className="px-3 py-1.5 bg-secondary hover:bg-secondary/95 text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-xs active:scale-[0.98]"
                          >
                            <span className="material-symbols-outlined text-[16px]">
                              {isPending ? 'rate_review' : 'edit_note'}
                            </span>
                            {isPending ? t('leaveFeedback') || 'Leave Review' : t('editFeedback') || 'Edit Review'}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* AI Tip / Clinical Intelligence */}
          <div 
            onClick={() => setShowTipModal(true)}
            className="bg-gradient-to-r from-primary to-primary-container text-white rounded-2xl p-lg shadow-md relative overflow-hidden interactive-card cursor-pointer group"
            title="Click to view detailed health guidelines"
          >
            <div className="absolute right-0 bottom-0 opacity-10 pointer-events-none transform translate-y-1/4 translate-x-1/4">
              <span className="material-symbols-outlined text-[200px]">lightbulb</span>
            </div>
            <div className="relative z-10 space-y-md">
              <span className="px-2.5 py-1 bg-white/20 rounded-full text-[10px] font-bold tracking-wider uppercase group-hover:scale-105 transition-transform inline-block">AI Daily Wellness Tip</span>
              <p className="font-body-lg text-lg leading-relaxed font-medium">
                "{dashboardData?.health_tip}"
              </p>
              <div className="flex items-center justify-between text-xs opacity-75">
                <span className="flex items-center gap-xs">
                  <span className="material-symbols-outlined text-[16px]">info</span>
                  <span>Powered by HealthAI Wellness Intelligence System</span>
                </span>
                <span className="font-bold underline text-[10px] group-hover:translate-x-1 transition-transform">Click for detail roadmap &rarr;</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Side: Activity Log & Quick Operations */}
        <div className="space-y-lg">
          {/* Medicine Reminders Card */}
          <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg interactive-card space-y-md">
            <h3 className="text-title-md font-bold text-primary flex items-center gap-xs border-b border-outline-variant/20 pb-2">
              <span className="material-symbols-outlined text-secondary">notifications_active</span>
              Medicine Reminders
            </h3>

            {/* Add Reminder Form */}
            <form onSubmit={async (e) => {
              e.preventDefault();
              const medicine_name = e.target.medicine_name.value;
              const dosage = e.target.dosage.value;
              const time = e.target.time.value;
              const method = e.target.method.value;
              const contact_info = e.target.contact_info.value || null;

              try {
                await api.createReminder({
                  medicine_name,
                  dosage,
                  time,
                  method,
                  contact_info,
                  days: "Daily"
                });
                alert("Reminder successfully set!");
                e.target.reset();
                loadReminders();
              } catch (err) {
                alert("Failed to create reminder: " + err.message);
              }
            }} className="space-y-sm text-xs">
              <div className="space-y-xs">
                <label className="font-bold text-outline uppercase block">Medicine Name</label>
                <input required type="text" name="medicine_name" placeholder="e.g. Paracetamol" className="w-full border border-outline-variant rounded p-2 bg-surface text-on-surface focus:border-primary outline-none" />
              </div>
              <div className="grid grid-cols-2 gap-sm">
                <div className="space-y-xs">
                  <label className="font-bold text-outline uppercase block">Dosage</label>
                  <input required type="text" name="dosage" placeholder="e.g. 1 pill, 5ml" className="w-full border border-outline-variant rounded p-2 bg-surface text-on-surface focus:border-primary outline-none" />
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
              <p className="text-center text-xs text-outline py-2">No medicine reminders configured.</p>
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
                          Dosage: {rem.dosage} | Daily: {rem.time}
                        </p>
                      </div>
                      
                      <div className="flex items-center gap-sm">
                        {/* Toggle Active Button */}
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
                          <span className="material-symbols-outlined text-[18px]">
                            {rem.is_active ? 'toggle_on' : 'toggle_off'}
                          </span>
                        </button>
                        
                        {/* Delete Button */}
                        <button
                          type="button"
                          onClick={async () => {
                            if (window.confirm(`Delete reminder for ${rem.medicine_name}?`)) {
                              try {
                                await api.deleteReminder(rem.id);
                                loadReminders();
                              } catch (err) {
                                alert("Failed to delete: " + err.message);
                              }
                            }
                          }}
                          className="p-1 hover:bg-error/10 text-error rounded-lg transition-colors focus:outline-none"
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

          {/* User Activity Logs */}
          <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm p-lg flex flex-col interactive-card">
            <h3 className="text-title-md font-bold text-primary mb-md flex items-center gap-xs">
              <span className="material-symbols-outlined text-secondary">history</span>
              Recent Activity
            </h3>
            
            <div className="space-y-md overflow-y-auto max-h-[220px]">
              {dashboardData?.activity_logs?.map((log, index) => (
                <div 
                  key={log.id || index} 
                  onClick={() => setSelectedActivity(log)}
                  className="flex gap-md items-center justify-between border-b border-outline-variant/10 pb-3 last:border-0 cursor-pointer hover:bg-surface-container-low/30 p-1.5 rounded-lg transition-colors w-full text-left"
                  title="Click to view activity details"
                >
                  <div className="flex gap-md items-start min-w-0">
                    <div className="w-8 h-8 rounded-full bg-secondary-container text-on-secondary-container flex items-center justify-center shrink-0">
                      <span className="material-symbols-outlined text-[16px]">
                        {log.action === "Appointment Booked" ? "calendar_today" : "info"}
                      </span>
                    </div>
                    <div className="min-w-0">
                      <h4 className="font-bold text-on-surface text-sm truncate">{log.action}</h4>
                      <p className="text-xs text-on-surface-variant mb-0.5 break-words">{log.details}</p>
                      <span className="text-[10px] text-outline font-semibold">
                        {new Date(log.timestamp).toLocaleString()}
                      </span>
                    </div>
                  </div>
                  {log.action === "Appointment Booked" && (
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); handleCancelAppointment(log.id); }}
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

      {/* Feedback Modal */}
      {currentFeedbackAppt && (
        <div className="fixed inset-0 bg-primary/20 backdrop-blur-sm flex items-center justify-center z-[100] animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl w-full max-w-lg border border-outline-variant shadow-2xl overflow-hidden interactive-card max-h-[90vh] flex flex-col">
            <div className="p-6 border-b border-outline-variant bg-surface flex justify-between items-center shrink-0">
              <h3 className="font-bold text-primary text-title-md flex items-center gap-xs">
                <span className="material-symbols-outlined text-secondary">rate_review</span>
                {isEditMode ? t('editFeedback') : t('feedbackTitle')}
              </h3>
              <button 
                onClick={() => setCurrentFeedbackAppt(null)}
                className="p-1 hover:bg-surface-container-high rounded-full transition-colors text-outline focus:outline-none"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            {feedbackSuccess ? (
              <div className="p-xl text-center space-y-md flex-1 flex flex-col items-center justify-center">
                <span className="material-symbols-outlined text-6xl text-success animate-bounce">check_circle</span>
                <div>
                  <h4 className="font-bold text-lg text-on-surface">{t('feedbackSubmitted')}</h4>
                </div>
              </div>
            ) : (
              <form onSubmit={handleConfirmFeedback} className="flex-1 overflow-y-auto p-6 space-y-md">
                <div className="flex items-center gap-md pb-md border-b border-outline-variant/30">
                  <div className="w-12 h-12 rounded-full overflow-hidden border border-outline-variant bg-surface-container flex items-center justify-center shrink-0">
                    <span className="material-symbols-outlined text-2xl text-outline font-fill fill-1">person</span>
                  </div>
                  <div>
                    <h4 className="font-bold text-on-surface">{currentFeedbackAppt.doctor?.name || 'Doctor'}</h4>
                    <p className="text-xs text-secondary font-semibold">{currentFeedbackAppt.doctor?.specialization}</p>
                    <p className="text-[10px] text-outline font-medium mt-0.5">Consultation date: {currentFeedbackAppt.date} at {currentFeedbackAppt.time}</p>
                  </div>
                </div>

                {/* Rating Selectors */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-md py-xs">
                  <div className="space-y-xs">
                    <span className="text-xs font-bold text-primary block">{t('overallRating')} *</span>
                    <div className="flex gap-xs">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <button
                          key={star}
                          type="button"
                          onClick={() => setRatingOverall(star)}
                          className="text-2xl transition-transform hover:scale-125 focus:outline-none"
                        >
                          <span 
                            className={`material-symbols-outlined ${star <= ratingOverall ? 'text-amber-500' : 'text-outline-variant/60'}`}
                            style={{ fontVariationSettings: star <= ratingOverall ? "'FILL' 1" : "'FILL' 0" }}
                          >
                            star
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-xs">
                    <span className="text-xs font-bold text-primary block">{t('doctorRating')} *</span>
                    <div className="flex gap-xs">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <button
                          key={star}
                          type="button"
                          onClick={() => setRatingDoctor(star)}
                          className="text-2xl transition-transform hover:scale-125 focus:outline-none"
                        >
                          <span 
                            className={`material-symbols-outlined ${star <= ratingDoctor ? 'text-amber-500' : 'text-outline-variant/60'}`}
                            style={{ fontVariationSettings: star <= ratingDoctor ? "'FILL' 1" : "'FILL' 0" }}
                          >
                            star
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Optional Category Ratings */}
                <div className="p-md bg-surface-container-lowest rounded-xl border border-outline-variant/30 space-y-md">
                  <h5 className="text-xs font-bold text-secondary uppercase tracking-wider">{t('optionalCategories')}</h5>
                  
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-sm">
                    {/* Communication */}
                    <div className="flex flex-col gap-1">
                      <span className="text-[11px] font-bold text-on-surface-variant">{t('ratingCommunication')}</span>
                      <div className="flex gap-1">
                        {[1, 2, 3, 4, 5].map((star) => (
                          <button
                            key={star}
                            type="button"
                            onClick={() => setRatingComm(star)}
                            className="text-lg focus:outline-none"
                          >
                            <span 
                              className={`material-symbols-outlined text-[20px] ${star <= ratingComm ? 'text-amber-500' : 'text-outline-variant/60'}`}
                              style={{ fontVariationSettings: star <= ratingComm ? "'FILL' 1" : "'FILL' 0" }}
                            >
                              star
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Professionalism */}
                    <div className="flex flex-col gap-1">
                      <span className="text-[11px] font-bold text-on-surface-variant">{t('ratingProfessionalism')}</span>
                      <div className="flex gap-1">
                        {[1, 2, 3, 4, 5].map((star) => (
                          <button
                            key={star}
                            type="button"
                            onClick={() => setRatingProf(star)}
                            className="text-lg focus:outline-none"
                          >
                            <span 
                              className={`material-symbols-outlined text-[20px] ${star <= ratingProf ? 'text-amber-500' : 'text-outline-variant/60'}`}
                              style={{ fontVariationSettings: star <= ratingProf ? "'FILL' 1" : "'FILL' 0" }}
                            >
                              star
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Wait Time */}
                    <div className="flex flex-col gap-1">
                      <span className="text-[11px] font-bold text-on-surface-variant">{t('ratingWaitTime')}</span>
                      <div className="flex gap-1">
                        {[1, 2, 3, 4, 5].map((star) => (
                          <button
                            key={star}
                            type="button"
                            onClick={() => setRatingWait(star)}
                            className="text-lg focus:outline-none"
                          >
                            <span 
                              className={`material-symbols-outlined text-[20px] ${star <= ratingWait ? 'text-amber-500' : 'text-outline-variant/60'}`}
                              style={{ fontVariationSettings: star <= ratingWait ? "'FILL' 1" : "'FILL' 0" }}
                            >
                              star
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Satisfaction */}
                    <div className="flex flex-col gap-1">
                      <span className="text-[11px] font-bold text-on-surface-variant">{t('ratingSatisfaction')}</span>
                      <div className="flex gap-1">
                        {[1, 2, 3, 4, 5].map((star) => (
                          <button
                            key={star}
                            type="button"
                            onClick={() => setRatingSat(star)}
                            className="text-lg focus:outline-none"
                          >
                            <span 
                              className={`material-symbols-outlined text-[20px] ${star <= ratingSat ? 'text-amber-500' : 'text-outline-variant/60'}`}
                              style={{ fontVariationSettings: star <= ratingSat ? "'FILL' 1" : "'FILL' 0" }}
                            >
                              star
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Written Review */}
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary">{t('commentsLabel')}</label>
                  <textarea 
                    value={comments}
                    onChange={(e) => setComments(e.target.value)}
                    placeholder={t('commentsPlaceholder')}
                    rows={3}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm font-semibold text-on-surface resize-none"
                  />
                </div>

                <p className="text-[10px] text-outline font-semibold leading-relaxed">
                  * {t('privacyDisclaimer')}
                </p>

                <div className="flex gap-sm border-t border-outline-variant/30 pt-md mt-md shrink-0">
                  <button
                    type="button"
                    onClick={() => setCurrentFeedbackAppt(null)}
                    className="flex-1 py-3 border border-outline hover:bg-surface-container-high font-bold text-xs rounded-lg transition-colors focus:outline-none active:scale-95"
                  >
                    {t('cancel')}
                  </button>
                  <button
                    type="submit"
                    disabled={feedbackLoading}
                    className="flex-1 py-3 bg-secondary hover:bg-secondary/95 text-white font-bold text-xs rounded-lg transition-colors flex items-center justify-center gap-xs focus:outline-none shadow-md active:scale-95"
                  >
                    {feedbackLoading ? (
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    ) : (
                      <>
                        <span className="material-symbols-outlined text-[16px]">done</span>
                        {isEditMode ? t('submitFeedback') : t('submitFeedback')}
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* AI Tip Wellness Insights Modal */}
      {showTipModal && (
        <div className="fixed inset-0 bg-primary/20 backdrop-blur-sm flex items-center justify-center z-[100] animate-in fade-in duration-200">
          <div className="bg-white dark:bg-[#111024] border border-outline-variant rounded-2xl w-full max-w-md shadow-2xl overflow-hidden p-lg space-y-md">
            <div className="flex justify-between items-center border-b border-outline-variant/30 pb-sm">
              <h3 className="font-bold text-primary text-title-md flex items-center gap-xs">
                <span className="material-symbols-outlined text-secondary">lightbulb</span>
                AI Wellness Insights
              </h3>
              <button 
                type="button"
                onClick={() => setShowTipModal(false)}
                className="p-1 hover:bg-surface-container-high rounded-full transition-colors text-outline focus:outline-none"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            
            <div className="space-y-sm">
              <span className="text-[10px] bg-primary/10 text-primary px-2.5 py-0.5 rounded font-bold uppercase tracking-wider block w-max">Active Recommendation</span>
              <p className="font-body-lg text-on-surface dark:text-white font-semibold leading-relaxed">
                "{dashboardData?.health_tip}"
              </p>
              <div className="h-px bg-outline-variant/20 my-md"></div>
              <h4 className="font-bold text-xs text-secondary uppercase tracking-wider">Clinical Context</h4>
              <p className="text-xs text-on-surface-variant leading-relaxed">
                This wellness tip is automatically compiled based on clinical health guidelines. Maintaining these healthy habits regularly helps improve cardiac metrics, sleep depth indices, and metabolic balance.
              </p>
            </div>

            <div className="flex gap-sm pt-sm border-t border-outline-variant/30 mt-lg">
              <button
                type="button"
                onClick={handleRefreshTip}
                disabled={refreshTipLoading}
                className="flex-1 py-2 border border-outline hover:bg-surface-container-high dark:text-white font-bold text-xs rounded-lg transition-colors flex items-center justify-center gap-xs focus:outline-none"
              >
                {refreshTipLoading ? (
                  <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
                ) : (
                  <>
                    <span className="material-symbols-outlined text-[16px]">refresh</span>
                    Get New Tip
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={() => setShowTipModal(false)}
                className="flex-1 py-2 bg-primary hover:bg-primary/95 text-white font-bold text-xs rounded-lg transition-colors focus:outline-none shadow-sm"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Activity Details Modal */}
      {selectedActivity && (
        <div className="fixed inset-0 bg-primary/20 backdrop-blur-sm flex items-center justify-center z-[100] animate-in fade-in duration-200">
          <div className="bg-white dark:bg-[#111024] border border-outline-variant rounded-2xl w-full max-w-sm shadow-2xl overflow-hidden p-lg space-y-md">
            <div className="flex justify-between items-center border-b border-outline-variant/30 pb-sm">
              <h3 className="font-bold text-primary text-sm flex items-center gap-xs">
                <span className="material-symbols-outlined text-secondary">history</span>
                Activity Detail
              </h3>
              <button 
                type="button"
                onClick={() => setSelectedActivity(null)}
                className="p-1 hover:bg-surface-container-high rounded-full transition-colors text-outline focus:outline-none"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            
            <div className="space-y-xs">
              <span className="text-[10px] text-outline font-bold uppercase tracking-wider block">Action</span>
              <h4 className="font-bold text-on-surface dark:text-white text-base">{selectedActivity.action}</h4>
              <span className="text-[10px] text-outline block">{new Date(selectedActivity.timestamp).toLocaleString()}</span>
              <div className="h-px bg-outline-variant/20 my-md"></div>
              <span className="text-[10px] text-outline font-bold uppercase tracking-wider block">Description Details</span>
              <p className="text-xs text-on-surface-variant leading-relaxed bg-surface-container-lowest dark:bg-white/5 p-sm rounded-lg border border-outline-variant/15">
                {selectedActivity.details}
              </p>
            </div>
            
            <div className="pt-sm border-t border-outline-variant/30 flex justify-end">
              <button
                type="button"
                onClick={() => setSelectedActivity(null)}
                className="px-6 py-2 bg-primary hover:bg-primary/95 text-white font-bold text-xs rounded-lg transition-colors focus:outline-none shadow-sm"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
