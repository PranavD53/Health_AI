import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LanguageProvider } from './context/LanguageContext';
import { WebSocketProvider } from './context/WebSocketContext';
import Layout from './components/Layout';

// Pages
import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';
import OtpVerify from './pages/OtpVerify';
import PatientDashboard from './pages/PatientDashboard';
import DoctorDashboard from './pages/DoctorDashboard';
import AdminDashboard from './pages/AdminDashboard';
import DoctorSearch from './pages/DoctorSearch';
import MedicalRecords from './pages/MedicalRecords';
import Settings from './pages/Settings';
import Chat from './pages/Chat';

function DashboardRedirect() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === 'doctor') {
    return <Navigate to={`/doctor/${user.doctor_profile_id}`} replace />;
  }
  return <Navigate to={`/${user.role}/${user.id}`} replace />;
}

function PatientRoute() {
  const { user } = useAuth();
  const { id } = useParams();
  
  if (!user) return <Navigate to="/login" replace />;
  
  if (user.role !== 'patient' || parseInt(id) !== user.id) {
    return <Navigate to={`/${user.role}/${user.id}`} replace />;
  }
  return <PatientDashboard />;
}

function DoctorRoute() {
  const { user } = useAuth();
  const { id } = useParams();
  
  if (!user) return <Navigate to="/login" replace />;
  
  if (user.role !== 'doctor' || parseInt(id) !== user.doctor_profile_id) {
    if (user.role === 'doctor') {
      return <Navigate to={`/doctor/${user.doctor_profile_id}`} replace />;
    }
    return <Navigate to={`/${user.role}/${user.id}`} replace />;
  }
  return <DoctorDashboard />;
}

function AdminRoute() {
  const { user } = useAuth();
  const { id } = useParams();
  
  if (!user) return <Navigate to="/login" replace />;
  
  if (user.role !== 'admin' || parseInt(id) !== user.id) {
    return <Navigate to={`/${user.role}/${user.id}`} replace />;
  }
  return <AdminDashboard />;
}

function AppointmentsRoute() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === 'admin' || user.role === 'doctor') {
    const targetId = user.role === 'doctor' ? user.doctor_profile_id : user.id;
    return <Navigate to={`/${user.role}/${targetId}`} replace />;
  }
  return <DoctorSearch />;
}

function RecordsRoute() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === 'admin') {
    return <Navigate to={`/${user.role}/${user.id}`} replace />;
  }
  return <MedicalRecords />;
}

function App() {
  return (
    <LanguageProvider>
      <Router>
        <AuthProvider>
          <WebSocketProvider>
            <Routes>
            {/* Public routes */}
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/otp-verify" element={<OtpVerify />} />

            {/* Redirect /dashboard to the specific role dashboard */}
            <Route path="/dashboard" element={<DashboardRedirect />} />

            {/* Role specific ID dashboards */}
            <Route 
              path="/patient/:id" 
              element={
                <Layout>
                  <PatientRoute />
                </Layout>
              } 
            />
            <Route 
              path="/doctor/:id" 
              element={
                <Layout>
                  <DoctorRoute />
                </Layout>
              } 
            />
            <Route 
              path="/admin/:id" 
              element={
                <Layout>
                  <AdminRoute />
                </Layout>
              } 
            />

            {/* Fallbacks if ID is missing */}
            <Route path="/patient" element={<Navigate to="/dashboard" replace />} />
            <Route path="/doctor" element={<Navigate to="/dashboard" replace />} />
            <Route path="/admin" element={<Navigate to="/dashboard" replace />} />

            {/* Other routes */}
            <Route 
              path="/appointments" 
              element={
                <Layout>
                  <AppointmentsRoute />
                </Layout>
              } 
            />
            <Route 
              path="/records" 
              element={
                <Layout>
                  <RecordsRoute />
                </Layout>
              } 
            />
            <Route 
              path="/chat" 
              element={
                <Layout>
                  <Chat />
                </Layout>
              } 
            />
            <Route 
              path="/settings" 
              element={
                <Layout>
                  <Settings />
                </Layout>
              } 
            />

            {/* Catch all - redirect to landing for unauthenticated, dashboard for authenticated */}
            <Route path="*" element={<PublicOrPrivateRedirect />} />
            </Routes>
          </WebSocketProvider>
        </AuthProvider>
      </Router>
  </LanguageProvider>
  );
}

function PublicOrPrivateRedirect() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/" replace />;
  const targetId = user.role === 'doctor' ? user.doctor_profile_id : user.id;
  return <Navigate to={`/${user.role}/${targetId}`} replace />;
}

export default App;
