import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, Button, StyleSheet, ScrollView } from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { api, Category, Church } from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function CreatePaymentScreen({ navigation }: any) {
  const { token } = useAuth();
  const [categories, setCategories] = useState<Category[]>([]);
  const [churches, setChurches] = useState<Church[]>([]);
  const [categoryId, setCategoryId] = useState('');
  const [churchId, setChurchId] = useState('');
  const [amount, setAmount] = useState('');
  const [paybill, setPaybill] = useState('');
  const [receipt, setReceipt] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!token) return;
    Promise.all([api.getCategories(token), api.getChurches(token)]).then(([cats, chs]) => {
      setCategories(cats.filter(c => c.is_active));
      setChurches(chs.filter(c => c.is_active));
    });
  }, [token]);

  async function submit() {
    if (!token || !categoryId || !churchId || !amount || !paybill || !receipt) {
      return;
    }
    setSaving(true);
    try {
      await api.createPayment(token, {
        church_id: Number(churchId),
        category_id: Number(categoryId),
        amount: Number(amount),
        paybill_number: paybill,
        receipt_reference: receipt,
        notes,
      });
      navigation.goBack();
    } finally {
      setSaving(false);
    }
  }

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.label}>Category</Text>
      <View style={styles.pickerContainer}>
        <Picker selectedValue={categoryId} onValueChange={setCategoryId}>
          <Picker.Item label="Select category" value="" />
          {categories.map(c => (
            <Picker.Item key={c.id} label={c.name} value={String(c.id)} />
          ))}
        </Picker>
      </View>

      <Text style={styles.label}>Church</Text>
      <View style={styles.pickerContainer}>
        <Picker selectedValue={churchId} onValueChange={setChurchId}>
          <Picker.Item label="Select church" value="" />
          {churches.map(c => (
            <Picker.Item key={c.id} label={c.name} value={String(c.id)} />
          ))}
        </Picker>
      </View>

      <Text style={styles.label}>Amount (KES)</Text>
      <TextInput style={styles.input} keyboardType="numeric" value={amount} onChangeText={setAmount} />

      <Text style={styles.label}>Paybill Number</Text>
      <TextInput style={styles.input} value={paybill} onChangeText={setPaybill} />

      <Text style={styles.label}>Receipt Reference</Text>
      <TextInput style={styles.input} value={receipt} onChangeText={setReceipt} />

      <Text style={styles.label}>Notes</Text>
      <TextInput style={styles.input} value={notes} onChangeText={setNotes} />

      <Button title={saving ? 'Saving...' : 'Save Payment'} onPress={submit} disabled={saving} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  label: { marginTop: 12, fontWeight: 'bold' },
  input: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 12, marginTop: 4 },
  pickerContainer: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, marginTop: 4, marginBottom: 12 },
});