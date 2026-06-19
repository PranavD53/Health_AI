import { resolveApiUrl } from '../utils/apiConfig';

const apiFetch = (path, options = {}) => fetch(resolveApiUrl(path), options);

const getHeaders = (isMultipart = false) => {
  const token = localStorage.getItem('access_token');
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (!isMultipart) {
    headers['Content-Type'] = 'application/json';
  }
  const appLang = localStorage.getItem('app_lang') || 'en';
  headers['Accept-Language'] = appLang;
  return headers;
};

const handleResponse = async (response) => {
  // Check if 401 occurs outside of login/verification endpoints
  if (response.status === 401 && !response.url.includes('/auth/login') && !response.url.includes('/auth/forgot-password-verify')) {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_role');
    localStorage.removeItem('is_verified');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  
  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch (err) {
    data = { message: text };
  }

  if (!response.ok) {
    let errorMsg = 'API request failed';
    if (data.detail) {
      if (typeof data.detail === 'string') {
        errorMsg = data.detail;
      } else if (Array.isArray(data.detail)) {
        // Handle validation errors from FastAPI
        errorMsg = data.detail.map(err => {
          const locStr = err.loc ? err.loc.join('.') : '';
          return locStr ? `${locStr}: ${err.msg}` : err.msg;
        }).join(', ');
      } else if (typeof data.detail === 'object') {
        errorMsg = JSON.stringify(data.detail);
      }
    } else if (data.message) {
      errorMsg = data.message;
    }
    throw new Error(errorMsg);
  }
  return data;
};

export const api = {
  // Auth endpoints
  login: async (email, password) => {
    const res = await apiFetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await handleResponse(res);
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    localStorage.setItem('user_role', data.role);
    localStorage.setItem('is_verified', data.is_verified ? 'true' : 'false');
    return data;
  },

  register: async (email, password, role) => {
    const res = await apiFetch('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, role })
    });
    return handleResponse(res);
  },

  verifyOtp: async (email, otp) => {
    const res = await apiFetch('/auth/verify-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, otp })
    });
    const data = await handleResponse(res);
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    localStorage.setItem('user_role', data.role);
    localStorage.setItem('is_verified', data.is_verified ? 'true' : 'false');
    return data;
  },

  logout: async () => {
    try {
      await apiFetch('/auth/logout', {
        method: 'POST',
        headers: getHeaders()
      });
    } catch (e) {
      console.error(e);
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_role');
    localStorage.removeItem('is_verified');
  },

  getMe: async () => {
    const res = await apiFetch('/auth/me', {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  toggleUserStatus: async (userId, isActive) => {
    const res = await apiFetch('/auth/toggle-status', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ user_id: userId, is_active: isActive })
    });
    return handleResponse(res);
  },

  // Profile endpoints
  getProfile: async (patientUserId = null) => {
    const url = patientUserId ? `/profile?patient_user_id=${patientUserId}` : '/profile';
    const res = await apiFetch(url, {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  createProfile: async (profileData) => {
    const res = await apiFetch('/profile', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(profileData)
    });
    return handleResponse(res);
  },

  updateProfile: async (profileData) => {
    const res = await apiFetch('/profile', {
      method: 'PUT',
      headers: getHeaders(),
      body: JSON.stringify(profileData)
    });
    return handleResponse(res);
  },

  // Doctor Registration
  registerDoctor: async (formData) => {
    const res = await apiFetch('/doctors/register', {
      method: 'POST',
      headers: getHeaders(true),
      body: formData
    });
    return handleResponse(res);
  },

  updateDoctorProfile: async (formData) => {
    const res = await apiFetch('/doctors/profile', {
      method: 'PUT',
      headers: getHeaders(true),
      body: formData
    });
    return handleResponse(res);
  },

  getDoctors: async (specialization = '') => {
    const url = specialization ? `/doctors?specialization=${specialization}` : '/doctors';
    const res = await apiFetch(url, {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  getPatientDashboard: async (lang = 'en') => {
    const res = await apiFetch(`/dashboard-data?lang=${lang}`, {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  getDoctorDashboard: async () => {
    const res = await apiFetch('/doctor/dashboard', {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  getAdminDashboard: async () => {
    const res = await apiFetch('/admin/dashboard', {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  verifyDoctor: async (id, status) => {
    const res = await apiFetch(`/admin/verify-doctor/${id}`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ status })
    });
    return handleResponse(res);
  },

  // Emergency SOS endpoints
  triggerSOS: async () => {
    const res = await apiFetch('/emergency/sos', {
      method: 'POST',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  getEmergencyAlerts: async () => {
    const res = await apiFetch('/emergency/alerts', {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  resolveEmergencyAlert: async (id) => {
    const res = await apiFetch(`/emergency/resolve/${id}`, {
      method: 'POST',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  // Complaints
  submitComplaint: async (message) => {
    const res = await apiFetch('/ai/complaint', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ message })
    });
    return handleResponse(res);
  },

  getComplaints: async () => {
    const res = await apiFetch('/admin/complaints', {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  resolveComplaint: async (id) => {
    const res = await apiFetch(`/admin/complaints/resolve/${id}`, {
      method: 'POST',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  // Appointments
  getAppointments: async (specialization = '') => {
    const url = specialization ? `/appointment/available-doctors?specialization=${specialization}` : '/appointment/available-doctors';
    const res = await apiFetch(url, {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  getMyAppointments: async () => {
    const res = await apiFetch('/appointment/my-appointments', {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  bookAppointment: async (doctorId, date, time) => {
    const res = await apiFetch('/appointment/book', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ doctor_id: doctorId, date, time })
    });
    return handleResponse(res);
  },

  cancelAppointment: async (id) => {
    const res = await apiFetch(`/appointment/cancel/${id}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  deleteAppointment: async (id) => {
    const res = await apiFetch(`/appointment/delete/${id}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  // Medical Records
  getRecords: async () => {
    const res = await apiFetch('/records/my-records', {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  uploadRecord: async (formData) => {
    const res = await apiFetch('/records/upload', {
      method: 'POST',
      headers: getHeaders(true),
      body: formData
    });
    return handleResponse(res);
  },

  // AI Assistant endpoint (Global Chatbot)
  sendAssistantMessage: async (message, groqKey = '', hfKey = '', language = '', onChunk = null) => {
    const payload = { message };
    if (groqKey) payload.groq_key = groqKey;
    if (hfKey) payload.hf_key = hfKey;
    if (language) payload.language = language;
    
    const res = await apiFetch('/ai/assistant', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      let errTxt = await res.text();
      throw new Error(errTxt || 'AI request failed');
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let result = { reply: '', action: null, disclaimer: '' };
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let newlineIdx;
      while ((newlineIdx = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, newlineIdx).trim();
        buffer = buffer.slice(newlineIdx + 1);
        if (line.startsWith('data: ')) {
          if (line === 'data: [DONE]') continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'chunk') {
              result.reply += data.content || '';
              if (onChunk) onChunk(result.reply);
            } else if (data.type === 'action') {
              result.action = data.action;
              result.disclaimer = data.disclaimer;
              if (data.reply) result.reply = data.reply;
            }
          } catch (e) {}
        }
      }
    }
    return result;
  },

  // AI Symptom analysis
  analyzeSymptom: async (symptoms, duration, severity) => {
    const res = await apiFetch('/ai/symptom-check', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ symptoms, duration, severity })
    });
    return handleResponse(res);
  },

  // Password Recovery Flow
  forgotPassword: async (email) => {
    const res = await apiFetch('/auth/forgot-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    return handleResponse(res);
  },

  forgotPasswordVerify: async (email, otp) => {
    const res = await apiFetch('/auth/forgot-password-verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, otp })
    });
    const data = await handleResponse(res);
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    localStorage.setItem('user_role', data.role);
    localStorage.setItem('is_verified', data.is_verified ? 'true' : 'false');
    return data;
  },

  // Admin promotions & request
  requestAdmin: async () => {
    const res = await apiFetch('/auth/request-admin', {
      method: 'POST',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  approveAdmin: async (userId) => {
    const res = await apiFetch(`/auth/admin/approve-admin/${userId}`, {
      method: 'POST',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  rejectAdmin: async (userId) => {
    const res = await apiFetch(`/auth/admin/reject-admin/${userId}`, {
      method: 'POST',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  // Cascade delete user history
  deleteUser: async (userId) => {
    const res = await apiFetch(`/auth/admin/users/${userId}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  resendOtp: async (email) => {
    const res = await apiFetch('/auth/resend-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    return handleResponse(res);
  },

  switchRole: async () => {
    const res = await apiFetch('/auth/switch-role', {
      method: 'POST',
      headers: getHeaders()
    });
    const data = await handleResponse(res);
    localStorage.setItem('user_role', data.role);
    return data;
  },

  getContacts: async () => {
    const res = await apiFetch('/chats/contacts', {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  getConversations: async () => {
    const res = await apiFetch('/chats/conversations', {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  getChatMessages: async (conversationId) => {
    const res = await apiFetch(`/chats/conversations/${conversationId}/messages`, {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  startConversation: async (targetUserId) => {
    const res = await apiFetch('/chats/conversations/start', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ target_user_id: targetUserId })
    });
    return handleResponse(res);
  },

  sendChatMessage: async (conversationId, formData) => {
    const res = await apiFetch(`/chats/conversations/${conversationId}/send`, {
      method: 'POST',
      headers: getHeaders(true),
      body: formData
    });
    return handleResponse(res);
  },

  deleteConversation: async (conversationId) => {
    const res = await apiFetch(`/chats/conversations/${conversationId}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  deleteMessage: async (conversationId, messageId) => {
    const res = await apiFetch(`/chats/conversations/${conversationId}/messages/${messageId}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  getNotifications: async () => {
    const res = await apiFetch('/chats/notifications', {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  markNotificationRead: async (notificationId) => {
    const res = await apiFetch(`/chats/notifications/${notificationId}/read`, {
      method: 'POST',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  markAllNotificationsRead: async () => {
    const res = await apiFetch('/chats/notifications/read-all', {
      method: 'POST',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  sendPrescription: async (conversationId, prescriptionData) => {
    const res = await apiFetch(`/chats/conversations/${conversationId}/prescription`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(prescriptionData)
    });
    return handleResponse(res);
  },

  analyzeRecord: async (recordId) => {
    const res = await apiFetch(`/records/${recordId}/analyze`, {
      method: 'POST',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  deleteRecord: async (recordId) => {
    const res = await apiFetch(`/records/${recordId}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  completeAppointment: async (id) => {
    const res = await apiFetch(`/appointment/complete/${id}`, {
      method: 'POST',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  submitFeedback: async (payload, edit = false) => {
    const res = await apiFetch(`/feedback/submit?edit=${edit}`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(payload)
    });
    return handleResponse(res);
  },

  getFeedbackForAppointment: async (apptId) => {
    const res = await apiFetch(`/feedback/appointment/${apptId}`, {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  getPendingFeedbacks: async () => {
    const res = await apiFetch('/feedback/pending', {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  getDoctorFeedbacks: async (docId) => {
    const res = await apiFetch(`/feedback/doctor/${docId}`, {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  getDoctorFeedbackAnalytics: async (docId) => {
    const res = await apiFetch(`/feedback/doctor/${docId}/analytics`, {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  getAdminFeedbacks: async () => {
    const res = await apiFetch('/feedback/admin/all', {
      method: 'GET',
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  moderateFeedback: async (id, isApproved) => {
    const res = await apiFetch(`/feedback/admin/moderate/${id}?is_approved=${isApproved}`, {
      method: 'POST',
      headers: getHeaders()
    });
    return handleResponse(res);
  }
};
