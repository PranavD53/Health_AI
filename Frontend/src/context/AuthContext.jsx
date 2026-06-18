import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [role, setRole] = useState(localStorage.getItem('user_role'));
  const [isVerified, setIsVerified] = useState(localStorage.getItem('is_verified') === 'true');
  const [loading, setLoading] = useState(true);

  const checkAuth = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setUser(null);
      setRole(null);
      setIsVerified(false);
      setLoading(false);
      return;
    }
    try {
      const userData = await api.getMe();
      setUser(userData);
      setRole(userData.role);
      setIsVerified(userData.is_verified);
      localStorage.setItem('user_role', userData.role);
      localStorage.setItem('is_verified', userData.is_verified ? 'true' : 'false');
    } catch (err) {
      console.error('Failed to authenticate:', err);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user_role');
      localStorage.removeItem('is_verified');
      setUser(null);
      setRole(null);
      setIsVerified(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  const loginUser = async (email, password) => {
    setLoading(true);
    try {
      const data = await api.login(email, password);
      setRole(data.role);
      setIsVerified(data.is_verified);
      await checkAuth();
      return data;
    } finally {
      setLoading(false);
    }
  };

  const logoutUser = async () => {
    setLoading(true);
    try {
      await api.logout();
    } finally {
      setUser(null);
      setRole(null);
      setIsVerified(false);
      setLoading(false);
      window.location.href = '/';
    }
  };

  return (
    <AuthContext.Provider value={{ user, role, isVerified, loading, login: loginUser, logout: logoutUser, checkAuth, setIsVerified }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
