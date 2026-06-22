import React, { createContext, useContext, useEffect, useState, useRef } from 'react';
import { useAuth } from './AuthContext';
import { getApiBaseUrl } from '../utils/apiConfig';

const WebSocketContext = createContext(null);

export function WebSocketProvider({ children }) {
  const { user } = useAuth();
  const [ws, setWs] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimeoutRef = useRef(null);
  const subscribersRef = useRef([]);

  const connect = () => {
    const token = localStorage.getItem('access_token');
    if (!token || !user) return;

    const apiBase = getApiBaseUrl() || `${window.location.protocol}//${window.location.host}`;
    const wsUrl = apiBase.replace(/^http/, 'ws') + `/ws?token=${token}`;

    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      
      // Ping interval to keep connection alive through proxies/NAT
      socket.pingInterval = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ event: 'ping' }));
        }
      }, 15000); // 15 seconds
    };

    socket.onmessage = (event) => {
      if (event.data === 'pong' || event.data === '{"event":"pong"}') return;
      try {
        const data = JSON.parse(event.data);
        subscribersRef.current.forEach((callback) => callback(data));
      } catch (e) {
        console.error('Failed to parse WebSocket message', e);
      }
    };

    socket.onclose = () => {
      console.log('WebSocket disconnected');
      if (socket.pingInterval) clearInterval(socket.pingInterval);
      setIsConnected(false);
      setWs(null);
      // Reconnect after 3 seconds if user is still logged in
      if (localStorage.getItem('access_token')) {
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
