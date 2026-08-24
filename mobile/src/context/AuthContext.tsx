import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

interface User {
  id: number;
  username: string;
  full_name: string;
  role: string;
  email: string;
  phone: string;
  region_id: number | null;
  region_name: string | null;
  sub_region_id: number | null;
  sub_region_name: string | null;
  church_id: number | null;
  church_name: string | null;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (data: { full_name?: string; email?: string; phone?: string }) => Promise<void>;
  changePassword: (current: string, newPass: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  loading: true,
  login: async () => {},
  logout: async () => {},
  updateProfile: async () => {},
  changePassword: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSession();
  }, []);

  async function loadSession() {
    try {
      const stored = await api.getToken();
      if (stored) {
        setToken(stored);
        const me = await api.me(stored);
        setUser(me);
      }
    } catch (e) {
      await api.clearToken();
    } finally {
      setLoading(false);
    }
  }

  async function login(username: string, password: string) {
    const data = await api.login(username, password);
    setToken(data.token);
    setUser(data.user);
    await api.saveToken(data.token);
  }

  async function logout() {
    if (token) {
      try { await api.logout(token); } catch {}
    }
    setToken(null);
    setUser(null);
    await api.clearToken();
  }

  async function updateProfile(data: { full_name?: string; email?: string; phone?: string }) {
    if (!token) throw new Error('Not authenticated');
    const updated = await api.updateProfile(token, data);
    setUser(prev => prev ? { ...prev, ...updated } : null);
  }

  async function changePassword(current: string, newPass: string) {
    if (!token) throw new Error('Not authenticated');
    await api.changePassword(token, current, newPass);
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, updateProfile, changePassword }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}