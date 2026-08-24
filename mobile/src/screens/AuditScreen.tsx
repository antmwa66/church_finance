import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, Button, StyleSheet, ScrollView, Picker, Alert } from 'react-native';
import { api, Payment } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

export default function AuditScreen({ navigation }: any) {
  const { user, token } = useAuth();
  const [payments, setPayments] = useState<any[]>([]);
  const [message, setMessage] = useState('');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) return;
    api.getAuditPayments(token).then(setPayments);
  }, [token]);

  async function verify() {
    if (!token || !message.trim()) return;
    setLoading(true);
    try {
      const res = await api.verifyBankMessage(token, message.trim());
      setResult(res);
    } catch (e: any) {
      Alert.alert('Error', e.message);
    } finally {
      setLoading(false);
    }
  }

  async function updateStatus(paymentId: number, status: string) {
    if (!token) return;
    try {
      await api.updateAuditStatus(token, paymentId, status);
      setPayments(prev => prev.map(p => p.id === paymentId ? { ...p, audit_status: status } : p));
      Alert.alert('Success', 'Status updated');
    } catch (e: any) {
      Alert.alert('Error', e.message);
    }
  }

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.heading}>Transaction Audit</Text>

      <View style={styles.card}>
        <Text style={styles.label}>Paste Bank / M-PESA Message</Text>
        <TextInput
          style={[styles.input, styles.textarea]}
          placeholder="Ksh 1,000 from JOHN DOE..."
          value={message}
          onChangeText={setMessage}
          multiline
          numberOfLines={4}
        />
        <Button title={loading ? 'Verifying...' : 'Verify'} onPress={verify} disabled={loading} />
      </View>

      {result && (
        <View style={styles.card}>
          <Text style={styles.subheading}>Parsed</Text>
          <Text>Amount: {result.parsed.amount}</Text>
          <Text>Paybill: {result.parsed.paybill_number}</Text>
          <Text>Date: {result.parsed.payment_date}</Text>
          <Text>Ref: {result.parsed.transaction_code}</Text>

          {result.matches?.length > 0 && (
            <View style={styles.matchBox}>
              <Text style={styles.matchTitle}>Exact Matches ({result.matches.length})</Text>
              {result.matches.map((m: any) => (
                <Text key={m.id}>#{m.id} KES {Number(m.amount).toLocaleString()} {m.receipt_reference}</Text>
              ))}
            </View>
          )}

          {result.potential_matches?.length > 0 && (
            <View style={styles.potentialBox}>
              <Text style={styles.potentialTitle}>Potential Matches ({result.potential_matches.length})</Text>
              {result.potential_matches.map((m: any) => (
                <Text key={m.id}>#{m.id} KES {Number(m.amount).toLocaleString()} {m.receipt_reference}</Text>
              ))}
            </View>
          )}

          {result.mismatches?.length > 0 && (
            <View style={styles.mismatchBox}>
              <Text style={styles.mismatchTitle}>Other Candidates ({result.mismatches.length})</Text>
              {result.mismatches.map((m: any) => (
                <Text key={m.id}>#{m.id} KES {Number(m.amount).toLocaleString()} {m.receipt_reference}</Text>
              ))}
            </View>
          )}
        </View>
      )}

      <Text style={styles.heading}>Payments</Text>
      {payments.map(p => (
        <View key={p.id} style={styles.card}>
          <Text style={styles.amount}>KES {Number(p.amount).toLocaleString()}</Text>
          <Text>{p.church_name} - {p.pastor_name}</Text>
          <Text>{p.payment_date} | {p.receipt_reference}</Text>
          <Text>Status: {p.audit_status || 'pending'}</Text>
          <View style={styles.statusRow}>
            {['pending', 'matched', 'mismatch', 'verified'].map(status => (
              <Button
                key={status}
                title={status}
                onPress={() => updateStatus(p.id, status)}
              />
            ))}
          </View>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  heading: { fontSize: 20, fontWeight: 'bold', marginVertical: 12 },
  subheading: { fontSize: 16, fontWeight: 'bold', marginTop: 8 },
  card: { backgroundColor: '#f2f2f2', padding: 12, borderRadius: 8, marginBottom: 12 },
  label: { fontWeight: 'bold', marginBottom: 4 },
  input: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 12, marginBottom: 8 },
  textarea: { height: 100, textAlignVertical: 'top' },
  amount: { fontWeight: 'bold', fontSize: 16 },
  statusRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 8 },
  matchBox: { backgroundColor: '#d4edda', padding: 8, borderRadius: 6, marginTop: 8 },
  matchTitle: { fontWeight: 'bold', color: '#155724' },
  potentialBox: { backgroundColor: '#fff3cd', padding: 8, borderRadius: 6, marginTop: 8 },
  potentialTitle: { fontWeight: 'bold', color: '#856404' },
  mismatchBox: { backgroundColor: '#f8d7da', padding: 8, borderRadius: 6, marginTop: 8 },
  mismatchTitle: { fontWeight: 'bold', color: '#721c24' },
});