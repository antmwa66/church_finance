import React, { useState } from 'react';
import { View, Text, TextInput, Button, StyleSheet, ScrollView, Alert } from 'react-native';
import { useAuth } from '../../context/AuthContext';

export default function ProfileScreen({ navigation }: any) {
  const { user, token, updateProfile, changePassword, logout } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [phone, setPhone] = useState(user?.phone || '');
  const [current, setCurrent] = useState('');
  const [newPass, setNewPass] = useState('');
  const [confirm, setConfirm] = useState('');
  const [saving, setSaving] = useState(false);

  async function saveProfile() {
    if (!token) return;
    setSaving(true);
    try {
      await updateProfile({ full_name: fullName, email, phone });
      Alert.alert('Success', 'Profile updated');
    } catch (e: any) {
      Alert.alert('Error', e.message);
    } finally {
      setSaving(false);
    }
  }

  async function change() {
    if (!token) return;
    setSaving(true);
    try {
      await changePassword(current, newPass);
      setCurrent(''); setNewPass(''); setConfirm('');
      Alert.alert('Success', 'Password changed');
    } catch (e: any) {
      Alert.alert('Error', e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleLogout() {
    await logout();
    navigation.replace('Login');
  }

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.heading}>Profile</Text>

      <Text style={styles.label}>Full Name</Text>
      <TextInput style={styles.input} value={fullName} onChangeText={setFullName} />

      <Text style={styles.label}>Email</Text>
      <TextInput style={styles.input} value={email} onChangeText={setEmail} autoCapitalize="none" />

      <Text style={styles.label}>Phone</Text>
      <TextInput style={styles.input} value={phone} onChangeText={setPhone} keyboardType="phone-pad" />

      <Button title={saving ? 'Saving...' : 'Update Profile'} onPress={saveProfile} disabled={saving} />

      <Text style={styles.heading}>Change Password</Text>
      <Text style={styles.label}>Current Password</Text>
      <TextInput style={styles.input} value={current} onChangeText={setCurrent} secureTextEntry />

      <Text style={styles.label}>New Password</Text>
      <TextInput style={styles.input} value={newPass} onChangeText={setNewPass} secureTextEntry />

      <Text style={styles.label}>Confirm New Password</Text>
      <TextInput style={styles.input} value={confirm} onChangeText={setConfirm} secureTextEntry />

      <Button title={saving ? 'Saving...' : 'Change Password'} onPress={change} disabled={saving} />
      <View style={{ height: 12 }} />
      <Button title="Logout" color="red" onPress={handleLogout} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  heading: { fontSize: 20, fontWeight: 'bold', marginVertical: 12 },
  label: { marginTop: 8, fontWeight: 'bold' },
  input: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 12, marginTop: 4 },
});