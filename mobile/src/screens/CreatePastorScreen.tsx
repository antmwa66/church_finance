import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, Button, StyleSheet, ScrollView } from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { api, Church } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

export default function CreatePastorScreen({ navigation }: any) {
  const { token } = useAuth();
  const [churches, setChurches] = useState<Church[]>([]);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [churchId, setChurchId] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!token) return;
    api.getChurches(token).then(setChurches);
  }, [token]);

  async function submit() {
    if (!token || !fullName || !username || !password || !churchId) return;
    setSaving(true);
    try {
      await api.createPastor(token, {
        full_name: fullName,
        email,
        phone,
        username,
        password,
        church_id: Number(churchId),
      });
      navigation.goBack();
    } finally {
      setSaving(false);
    }
  }

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.label}>Full Name</Text>
      <TextInput style={styles.input} value={fullName} onChangeText={setFullName} />

      <Text style={styles.label}>Email</Text>
      <TextInput style={styles.input} value={email} onChangeText={setEmail} autoCapitalize="none" />

      <Text style={styles.label}>Phone</Text>
      <TextInput style={styles.input} value={phone} onChangeText={setPhone} keyboardType="phone-pad" />

      <Text style={styles.label}>Username</Text>
      <TextInput style={styles.input} value={username} onChangeText={setUsername} autoCapitalize="none" />

      <Text style={styles.label}>Password</Text>
      <TextInput style={styles.input} value={password} onChangeText={setPassword} secureTextEntry />

      <Text style={styles.label}>Church</Text>
      <View style={styles.pickerContainer}>
        <Picker selectedValue={churchId} onValueChange={setChurchId}>
          <Picker.Item label="Select church" value="" />
          {churches.map(c => (
            <Picker.Item key={c.id} label={c.name} value={String(c.id)} />
          ))}
        </Picker>
      </View>

      <Button title={saving ? 'Saving...' : 'Create Pastor'} onPress={submit} disabled={saving} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  label: { marginTop: 12, fontWeight: 'bold' },
  input: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 12, marginTop: 4 },
  pickerContainer: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, marginTop: 4, marginBottom: 12 },
});