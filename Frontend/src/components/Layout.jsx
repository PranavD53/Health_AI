import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import TopNavBar from './TopNavBar';
import SideNavBar from './SideNavBar';
import GlobalAssistant from './GlobalAssistant';

export default function Layout({ children }) {
  const { user, isVerified, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!loading) {
      if (!user) {
        navigate('/login');
      } else if (!isVerified && location.pathname !== '/otp-verify') {
        navigate('/otp-verify');
      }
    }
  }, [user, isVerified, loading, navigate, location.pathname]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center space-y-4">
        <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
        <p className="text-primary font-bold">HealthAI is loading...</p>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background relative overflow-x-hidden transition-colors duration-300">
      <TopNavBar />
      <div className="flex pt-16 relative z-10">
        <SideNavBar />
        <main className="flex-1 lg:pl-72 min-h-[calc(100vh-64px)] p-margin-mobile md:p-gutter">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
      <div className="wave-mesh-bg" />
      <GlobalAssistant />
    </div>
  );
}
