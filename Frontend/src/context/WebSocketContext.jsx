import React, { createContext, useContext, useEffect, useState, useRef } from 'react';
import { useAuth } from './AuthContext';

const WebSocketContext = createContext(null);

export function WebSocketProvider({ children }) {
  const { user } = useAuth();
  const [ws, setWs] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimeoutRef = useRef(null);
  const subscribersRef = useRef([]);

  const connect = () => {
    const token = localStorage.getItem('token');
    if (!token || !user) return;

    // Use wss:// for https://, ws:// for http://
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // If running Vite dev server, we usually proxy. However WebSocket needs absolute URL or relative WS URL
    // We'll use the API base URL but change protocol.
    const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
    const wsUrl = apiBase.replace(/^http/, 'ws') + `/ws?token=${token}`;

    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        subscribersRef.current.forEach((callback) => callback(data));
      } catch (e) {
        console.error('Failed to parse WebSocket message', e);
      }
    };

    socket.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
      setWs(null);
      // Reconnect after 3 seconds if user is still logged in
      if (localStorage.getItem('token')) {
        reconnectTimeoutRef.current = setTimeout(connect, 3000);
      }
    };

    socket.onerror = (err) => {
      console.error('WebSocket error:', err);
      socket.close();
    };

    setWs(socket);
  };

  useEffect(() => {
    if (user) {
      connect();
    } else {
      if (ws) {
        ws.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    }
    return () => {
      if (ws) {
        ws.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [user]);

  const subscribe = (callback) => {
    subscribersRef.current.push(callback);
    return () => {
      subscribersRef.current = subscribersRef.current.filter((cb) => cb !== callback);
    };
  };

  return (
    <WebSocketContext.Provider value={{ ws, isConnected, subscribe }}>
      {children}
    </WebSocketContext.Provider>
  );
}

export const useWebSocket = () => useContext(WebSocketContext);
