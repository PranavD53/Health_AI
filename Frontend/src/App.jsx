import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LanguageProvider } from './context/LanguageContext';
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

function DashboardSwitch() {
  const { user } = useAuth();
  
  if (!user) return null;
  
  if (user.role === 'patient') {
    return <PatientDashboard />;
  } else if (user.role === 'doctor') {
    return <DoctorDashboard />;
  } else if (user.role === 'admin') {
    return <AdminDashboard />;
  }
  
  return <Navigate to="/login" replace />;
}

function AppointmentsRoute() {
  const { user } = useAuth();
  if (!user) return null;
  if (user.role === 'admin' || user.role === 'doctor') return <Navigate to="/dashboard" replace />;
  return <DoctorSearch />;
}

function RecordsRoute() {
  const { user } = useAuth();
  if (!user) return null;
  if (user.role === 'admin') return <Navigate to="/dashboard" replace />;
  return <MedicalRecords />;
}

function App() {
  return (
    <LanguageProvider>
      <Router>
        <AuthProvider>
          <Routes>
          {/* Public routes */}
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/otp-verify" element={<OtpVerify />} />

          {/* Protected routes wrapped in Layout */}
          <Route 
            path="/dashboard" 
            element={
              <Layout>
                <DashboardSwitch />
              </Layout>
            } 
          />
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
      </AuthProvider>
    </Router>
  </LanguageProvider>
  );
}

function PublicOrPrivateRedirect() {
  const { user } = useAuth();
  return user ? <Navigate to="/dashboard" replace /> : <Navigate to="/" replace />;
}

export default App;
