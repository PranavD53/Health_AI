import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';

export default function AdminDashboard() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const [dashboardData, setDashboardData] = useState(null);
  const [complaints, setComplaints] = useState([]);
  const [activeSubTab, setActiveSubTab] = useState('verifications'); // verifications, users, complaints
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const loadData = async () => {
    try {
      const data = await api.getAdminDashboard();
      setDashboardData(data);

      const compList = await api.getComplaints();
      setComplaints(compList);
    } catch (err) {
      console.error(err);
      setError("Failed to load administration controls.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleVerifyDoctor = async (id, status) => {
    setError('');
    setSuccessMsg('');
    try {
      await api.verifyDoctor(id, status);
      setSuccessMsg(`Doctor successfully ${status === 'verified' ? 'approved' : 'rejected'}.`);
      loadData();
    } catch (err) {
      setError("Failed to update verification: " + err.message);
    }
  };

  const handleToggleUser = async (userId, currentActive) => {
    setError('');
    setSuccessMsg('');
    try {
      await api.toggleUserStatus(userId, !currentActive);
      setSuccessMsg(`User account status successfully updated.`);
      loadData();
    } catch (err) {
      setError("Failed to update status: " + err.message);
    }
  };

  const handleResolveComplaint = async (id) => {
    setError('');
    setSuccessMsg('');
    try {
      await api.resolveComplaint(id);
      setSuccessMsg(`Complaint resolved.`);
      loadData();
    } catch (err) {
      setError("Failed to resolve complaint: " + err.message);
    }
  };

  const handleApproveAdmin = async (userId) => {
    setError('');
    setSuccessMsg('');
    try {
      const res = await api.approveAdmin(userId);
      setSuccessMsg(res.message || "User successfully promoted to admin.");
      loadData();
    } catch (err) {
      setError("Failed to approve admin request: " + err.message);
    }
  };

  const handleRejectAdmin = async (userId) => {
    setError('');
    setSuccessMsg('');
    try {
      const res = await api.rejectAdmin(userId);
      setSuccessMsg(res.message || "Admin request rejected.");
      loadData();
    } catch (err) {
      setError("Failed to reject admin request: " + err.message);
    }
  };

  const handleDeleteUser = async (userId) => {
    const confirmed = window.confirm("Are you sure you want to permanently delete this user account and all their medical, appointment, and communication history? This action is irreversible.");
    if (!confirmed) return;

    setError('');
    setSuccessMsg('');
    try {
      const res = await api.deleteUser(userId);
      setSuccessMsg(res.message || "User and all associated history successfully deleted.");
      loadData();
    } catch (err) {
      setError("Failed to delete user: " + err.message);
    }
  };

  const handleCancelAppointment = async (apptId) => {
    const confirmed = window.confirm("Are you sure you want to cancel this appointment?");
    if (!confirmed) return;

    setError('');
    setSuccessMsg('');
    try {
      await api.cancelAppointment(apptId);
      setSuccessMsg("Appointment successfully cancelled.");
      loadData();
    } catch (err) {
      setError("Failed to cancel appointment: " + err.message);
    }
  };

  if (loading) {
    return (
      <div className="space-y-xl animate-pulse">
        <div className="h-12 bg-surface-container rounded-xl w-1/3"></div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-md">
          {[1, 2, 3, 4].map(i => <div key={i} className="h-24 bg-surface-container rounded-xl"></div>)}
        </div>
        <div className="h-96 bg-surface-container rounded-xl"></div>
      </div>
    );
  }

  return (
    <div className="space-y-xl animate-in fade-in duration-300">
      <header>
        <h2 className="text-on-surface font-headline-lg text-headline-lg">
          {t('adminPortal')}
        </h2>
        <p className="text-on-surface-variant font-body-md text-body-md">Configure user access roles, verify clinician documents, and inspect feedback complaints.</p>
      </header>

      {error && (
        <div className="p-4 bg-error-container text-on-error-container rounded-xl flex items-center gap-sm">
          <span className="material-symbols-outlined">error</span>
          <p>{error}</p>
        </div>
      )}

      {successMsg && (
        <div className="p-4 bg-success/10 text-success rounded-xl flex items-center gap-sm font-bold text-sm">
          <span className="material-symbols-outlined">check_circle</span>
          <p>{successMsg}</p>
        </div>
      )}

      {/* Stats Bento Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-md">
        <div className="bg-white border border-outline-variant/30 p-6 rounded-2xl shadow-sm interactive-card">
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <span className="material-symbols-outlined">person</span>
            </div>
          </div>
          <p className="text-xs text-outline font-semibold uppercase">Total Patients</p>
          <h2 className="text-2xl font-bold text-primary">{dashboardData?.total_patients}</h2>
        </div>

        <div className="bg-white border border-outline-variant/30 p-6 rounded-2xl shadow-sm interactive-card">
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 bg-secondary/10 rounded-lg text-secondary">
              <span className="material-symbols-outlined">medical_services</span>
            </div>
          </div>
          <p className="text-xs text-outline font-semibold uppercase">Total Doctors</p>
          <h2 className="text-2xl font-bold text-primary">{dashboardData?.total_doctors}</h2>
        </div>

        <div className="bg-white border border-outline-variant/30 p-6 rounded-2xl shadow-sm interactive-card">
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 bg-error/10 rounded-lg text-error animate-pulse">
              <span className="material-symbols-outlined">pending_actions</span>
            </div>
          </div>
          <p className="text-xs text-outline font-semibold uppercase">Pending Approvals</p>
          <h2 className="text-2xl font-bold text-primary">{dashboardData?.pending_verifications}</h2>
        </div>

        <div className="bg-white border border-outline-variant/30 p-6 rounded-2xl shadow-sm interactive-card">
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 bg-tertiary-fixed rounded-lg text-tertiary">
              <span className="material-symbols-outlined">network_check</span>
            </div>
          </div>
          <p className="text-xs text-outline font-semibold uppercase">Active Sessions</p>
          <h2 className="text-2xl font-bold text-primary">{dashboardData?.active_sessions}</h2>
        </div>
      </div>

      {/* Control Tabs */}
      <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm overflow-hidden interactive-card">
        <div className="border-b border-outline-variant/30 bg-surface flex overflow-x-auto">
          <button
            onClick={() => setActiveSubTab('verifications')}
            className={`px-6 py-4 font-bold text-sm flex items-center gap-xs focus:outline-none transition-colors border-b-2 ${activeSubTab === 'verifications' ? 'border-primary text-primary' : 'border-transparent text-outline hover:text-on-surface'
              }`}
          >
            <span className="material-symbols-outlined">verified_user</span>
            Verification Queue ({dashboardData?.verification_queue?.length || 0})
          </button>

          <button
            onClick={() => setActiveSubTab('users')}
            className={`px-6 py-4 font-bold text-sm flex items-center gap-xs focus:outline-none transition-colors border-b-2 ${activeSubTab === 'users' ? 'border-primary text-primary' : 'border-transparent text-outline hover:text-on-surface'
              }`}
          >
            <span className="material-symbols-outlined">group</span>
            User Management ({dashboardData?.users?.length || 0})
          </button>

          <button
            onClick={() => setActiveSubTab('complaints')}
            className={`px-6 py-4 font-bold text-sm flex items-center gap-xs focus:outline-none transition-colors border-b-2 ${activeSubTab === 'complaints' ? 'border-primary text-primary' : 'border-transparent text-outline hover:text-on-surface'
              }`}
          >
            <span className="material-symbols-outlined">support_agent</span>
            Patient Complaints ({complaints.filter(c => c.status === 'pending').length || 0})
          </button>


        </div>

        <div className="p-lg">
          {/* 1. Verifications Queue Tab */}
          {activeSubTab === 'verifications' && (
            <div className="space-y-md">
              {dashboardData?.verification_queue?.length === 0 ? (
                <div className="text-center py-xl text-outline font-semibold">
                  <span className="material-symbols-outlined text-4xl mb-xs">verified</span>
                  <p>All doctor registration verifications are complete.</p>
                </div>
              ) : (
                <div className="divide-y divide-outline-variant/20">
                  {dashboardData?.verification_queue?.map(req => (
                    <div key={req.id} className="py-md flex flex-col md:flex-row justify-between items-start md:items-center gap-md">
                      <div>
                        <h4 className="font-bold text-on-surface">{req.doctor_name}</h4>
                        <p className="text-xs text-secondary font-semibold">{req.specialization} | Experience: {req.experience_years} Years</p>
                        {req.license_number && (
                          <p className="text-xs text-primary font-bold mt-xs">Doctor ID / License: {req.license_number}</p>
                        )}
                        <p className="text-xs text-outline font-medium mt-xs">Email Contact: {req.contact}</p>
                      </div>

                      <div className="flex gap-md items-center w-full md:w-auto">
                        <button
                          onClick={() => {
                            if (req.license_document_path) {
                              const docUrl = req.license_document_path;
                              const win = window.open(docUrl, '_blank');
                              if (!win) alert("Popup blocked. Please allow popups to view documentation.");
                            } else {
                              alert("No license document path uploaded.");
                            }
                          }}
                          className="px-3 py-1.5 border border-outline-variant hover:bg-surface-container text-xs font-semibold rounded-lg flex items-center gap-xs focus:outline-none"
                        >
                          <span className="material-symbols-outlined text-[16px]">file_open</span>
                          View Documents
                        </button>

                        <button
                          onClick={() => handleVerifyDoctor(req.id, 'verified')}
                          className="px-3 py-1.5 bg-success text-white text-xs font-bold rounded-lg hover:opacity-90 focus:outline-none"
                        >
                          Approve
                        </button>

                        <button
                          onClick={() => handleVerifyDoctor(req.id, 'rejected')}
                          className="px-3 py-1.5 bg-error text-on-error text-xs font-bold rounded-lg hover:opacity-90 focus:outline-none"
                        >
                          Reject
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 2. User Management Tab */}
          {activeSubTab === 'users' && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-outline-variant/30 text-outline">
                    <th className="py-3 font-semibold">User Email</th>
                    <th className="py-3 font-semibold">Role</th>
                    <th className="py-3 font-semibold">Status</th>
                    <th className="py-3 font-semibold text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-outline-variant/10">
                  {dashboardData?.users?.map(u => (
                    <tr key={u.id}>
                      <td className="py-3.5 font-bold text-on-surface">
                        <div className="flex flex-col">
                          <span>{u.email}</span>
                          {u.role === 'doctor' && u.doctor_name && (
                            <span className="text-xs text-secondary font-semibold">
                              {u.doctor_name} ({u.specialization || 'General'})
                            </span>
                          )}
                        </div>
                        {u.admin_requested && (
                          <span className="ml-sm inline-flex items-center gap-0.5 border border-amber-300 bg-amber-50 text-amber-800 text-[10px] font-bold px-1.5 py-0.5 rounded-full animate-pulse">
                            <span className="material-symbols-outlined text-[10px]">pending</span>
                            Admin Requested
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 capitalize text-secondary font-semibold">{u.role}</td>
                      <td className="py-3.5">
                        <div className="flex flex-col gap-xs">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold text-center w-28 ${u.is_active ? 'bg-success/10 text-success' : 'bg-error-container/20 text-error'
                            }`}>
                            {u.is_active ? 'Active' : 'Deactivated'}
                          </span>
                          {u.role === 'doctor' && (
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold text-center w-28 capitalize ${
                              u.verification_status === 'verified' ? 'bg-emerald-100 text-emerald-800' : 
                              u.verification_status === 'rejected' ? 'bg-error-container/40 text-error' : 
                              'bg-amber-100 text-amber-800 animate-pulse'
                            }`}>
                              License: {u.verification_status || 'pending'}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3.5 text-right">
                        <div className="flex items-center justify-end gap-sm flex-wrap">
                          {u.role === 'doctor' && (
                            <>
                              {u.license_document_path && (
                                <a
                                  href={u.license_document_path}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="px-2.5 py-1 bg-surface-container-high hover:bg-surface-container-highest text-secondary border border-outline-variant/35 text-xs font-bold rounded-lg transition-colors flex items-center gap-0.5 shadow-sm"
                                  title="View Uploaded License Document"
                                >
                                  <span className="material-symbols-outlined text-[14px]">description</span>
                                  License Doc
                                </a>
                              )}
                              {u.verification_status !== 'verified' ? (
                                <button
                                  onClick={() => handleVerifyDoctor(u.verification_id || u.id, 'verified')}
                                  className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-0.5 animate-in fade-in duration-200"
                                >
                                  <span className="material-symbols-outlined text-[14px]">verified</span>
                                  Approve
                                </button>
                              ) : (
                                <button
                                  onClick={() => handleVerifyDoctor(u.verification_id || u.id, 'rejected')}
                                  className="px-2.5 py-1 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-0.5 animate-in fade-in duration-200"
                                >
                                  <span className="material-symbols-outlined text-[14px]">gavel</span>
                                  Revoke License
                                </button>
                              )}
                            </>
                          )}
                          {u.admin_requested && (
                            <>
                              <button
                                onClick={() => handleApproveAdmin(u.id)}
                                disabled={user?.email !== 'sricharanpranav1@gmail.com'}
                                className="px-2.5 py-1 bg-success hover:bg-success/90 disabled:opacity-40 disabled:hover:bg-success text-white text-[11px] font-bold rounded-lg transition-all flex items-center gap-0.5"
                                title={user?.email !== 'sricharanpranav1@gmail.com' ? "Only the system superadmin can approve admin promotion requests" : "Approve admin request"}
                              >
                                <span className="material-symbols-outlined text-[12px]">done</span>
                                Approve Admin
                              </button>
                              <button
                                onClick={() => handleRejectAdmin(u.id)}
                                disabled={user?.email !== 'sricharanpranav1@gmail.com'}
                                className="px-2.5 py-1 bg-amber-600 hover:bg-amber-700 disabled:opacity-40 disabled:hover:bg-amber-600 text-white text-[11px] font-bold rounded-lg transition-all flex items-center gap-0.5"
                                title={user?.email !== 'sricharanpranav1@gmail.com' ? "Only the system superadmin can reject admin promotion requests" : "Reject admin request"}
                              >
                                <span className="material-symbols-outlined text-[12px]">close</span>
                                Reject
                              </button>
                            </>
                          )}
                          <button
                            onClick={() => handleToggleUser(u.id, u.is_active)}
                            className={`px-2.5 py-1 text-xs font-bold rounded-lg ${u.is_active ? 'border border-error/20 text-error hover:bg-error/5' : 'bg-primary text-white hover:opacity-95'
                              }`}
                          >
                            {u.is_active ? 'Deactivate' : 'Activate'}
                          </button>
                          {u.id !== user?.id && (
                            <button
                              onClick={() => handleDeleteUser(u.id)}
                              className="px-2.5 py-1 bg-error hover:bg-error/95 text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-0.5 animate-in fade-in duration-200"
                            >
                              <span className="material-symbols-outlined text-[12px]">delete</span>
                              Delete User
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 3. Patients Complaints Tab */}
          {activeSubTab === 'complaints' && (
            <div className="space-y-md">
              {complaints.length === 0 ? (
                <p className="text-center py-xl text-outline font-semibold">No complaints registered in the system inbox.</p>
              ) : (
                <div className="divide-y divide-outline-variant/20">
                  {complaints.map(c => (
                    <div key={c.id} className="py-md flex flex-col md:flex-row justify-between items-start gap-md">
                      <div className="space-y-xs max-w-2xl">
                        <div className="flex items-center gap-sm">
                          <span className="font-bold text-primary text-sm">{c.user_email}</span>
                          <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase ${c.status === 'resolved' ? 'bg-success/10 text-success' : 'bg-error-container/20 text-error'
                            }`}>
                            {c.status}
                          </span>
                        </div>
                        <p className="text-xs text-on-surface font-medium leading-relaxed bg-surface-container-low p-md rounded-xl">
                          "{c.message}"
                        </p>
                        <span className="text-[10px] text-outline block">
                          Submitted: {new Date(c.created_at).toLocaleString()}
                        </span>
                      </div>

                      {c.status === 'pending' && (
                        <button
                          onClick={() => handleResolveComplaint(c.id)}
                          className="px-3 py-1.5 bg-secondary text-white text-xs font-bold rounded-lg hover:opacity-90 focus:outline-none whitespace-nowrap self-center"
                        >
                          Mark Resolved
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}


        </div>
      </div>
    </div>
  );
}
