import AsyncStorage from '@react-native-async-storage/async-storage';

const DEV_API_URL = '10.88.51.20';
const API_BASE_URL = __DEV__ ? `http://${DEV_API_URL}:5000` : '10.88.51.20';

export interface Category {
  id: number;
  name: string;
  description: string;
  is_active: boolean;
}

export interface Church {
  id: number;
  name: string;
  sub_region_id: number;
  is_active: boolean;
}

export interface Pastor {
  id: number;
  full_name: string;
  email: string;
  phone: string;
  church_id: number;
  church_name: string;
  sub_region_id: number;
  is_active: boolean;
}

export interface Payment {
  id: number;
  amount: number;
  paybill_number: string;
  receipt_reference: string;
  payment_date: string;
  notes: string;
  church_id: number;
  church_name: string;
  category_id: number;
  category_name: string;
  pastor_id: number;
  pastor_name: string;
}

export interface ReportItem {
  region_name: string;
  sub_region_name: string;
  allocation: number;
  contributed: number;
  balance: number;
  percentage: number;
}

async function request(path: string, options: RequestInit = {}, token?: string) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  const text = await res.text();
  let data: any = {};
  try { data = JSON.parse(text); } catch {}
  if (!res.ok) throw new Error(data.error || text || 'Request failed');
  return data;
}

export const api = {
  async saveToken(token: string) {
    await AsyncStorage.setItem('auth_token', token);
  },

  async getToken() {
    return await AsyncStorage.getItem('auth_token');
  },

  async clearToken() {
    await AsyncStorage.removeItem('auth_token');
  },

  async login(username: string, password: string) {
    return request('/api/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  },

  async logout(token: string) {
    return request('/api/logout', { method: 'POST' }, token);
  },

  async me(token: string) {
    return request('/api/me', {}, token);
  },

  async dashboard(token: string) {
    return request('/api/dashboard', {}, token);
  },

  async getSubRegions(token: string) {
    return request('/api/sub_regions', {}, token);
  },

  async createSubRegion(token: string, data: { name: string; region_id?: number }) {
    return request('/api/sub_regions', { method: 'POST', body: JSON.stringify(data) }, token);
  },

  async updateSubRegion(token: string, id: number, data: { name?: string; is_active?: boolean }) {
    return request(`/api/sub_regions/${id}`, { method: 'PUT', body: JSON.stringify(data) }, token);
  },

  async deleteSubRegion(token: string, id: number) {
    return request(`/api/sub_regions/${id}`, { method: 'DELETE' }, token);
  },

  async getChurches(token: string) {
    return request('/api/churches', {}, token);
  },

  async createChurch(token: string, data: { name: string; sub_region_id: number }) {
    return request('/api/churches', { method: 'POST', body: JSON.stringify(data) }, token);
  },

  async updateChurch(token: string, id: number, data: { name?: string; is_active?: boolean }) {
    return request(`/api/churches/${id}`, { method: 'PUT', body: JSON.stringify(data) }, token);
  },

  async deleteChurch(token: string, id: number) {
    return request(`/api/churches/${id}`, { method: 'DELETE' }, token);
  },

  async getPastors(token: string) {
    return request('/api/pastors', {}, token);
  },

  async createPastor(token: string, data: {
    full_name: string;
    email?: string;
    phone?: string;
    username: string;
    password: string;
    church_id: number;
    sub_region_id?: number;
    region_id?: number;
  }) {
    return request('/api/pastors', { method: 'POST', body: JSON.stringify(data) }, token);
  },

  async updatePastor(token: string, id: number, data: {
    full_name?: string;
    email?: string;
    phone?: string;
    church_id?: number;
    is_active?: boolean;
  }) {
    return request(`/api/pastors/${id}`, { method: 'PUT', body: JSON.stringify(data) }, token);
  },

  async deletePastor(token: string, id: number) {
    return request(`/api/pastors/${id}`, { method: 'DELETE' }, token);
  },

  async createPayment(token: string, data: {
    church_id: number;
    category_id: number;
    amount: number;
    paybill_number: string;
    receipt_reference: string;
    payment_date?: string;
    notes?: string;
  }) {
    return request('/api/payments', { method: 'POST', body: JSON.stringify(data) }, token);
  },

  async getPayments(token: string) {
    return request('/api/payments', {}, token);
  },

  async getReports(token: string, categoryId?: number) {
    const qs = categoryId ? `?category_id=${encodeURIComponent(String(categoryId))}` : '';
    return request(`/api/reports/regions${qs}`, {}, token);
  },

  async getCategories(token: string) {
    return request('/api/categories', {}, token);
  },

  async updateProfile(token: string, data: { full_name?: string; email?: string; phone?: string }) {
    return request('/api/profile', { method: 'PUT', body: JSON.stringify(data) }, token);
  },

  async changePassword(token: string, current: string, newPass: string) {
    const res = await request('/api/profile/password', {
      method: 'POST',
      body: JSON.stringify({ current_password: current, new_password: newPass, confirm_password: newPass }),
    }, token);
    return res;
  },

  async getAuditPayments(token: string) {
    return request('/api/audit/payments', {}, token);
  },

  async verifyBankMessage(token: string, message: string) {
    return request('/api/audit/verify', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }, token);
  },

  async updateAuditStatus(token: string, paymentId: number, status: string, notes?: string) {
    return request(`/api/audit/payments/${paymentId}/status`, {
      method: 'POST',
      body: JSON.stringify({ audit_status: status, audit_notes: notes }),
    }, token);
  },
};