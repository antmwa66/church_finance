import React, { useEffect, useState } from 'react';
import { View, Text, Button, StyleSheet, ScrollView } from 'react-native';
import { api, Payment } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

export default function PaymentsScreen({ navigation }: any) {
  const { token } = useAuth();
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    if (!token) return;
    try {
      const data = await api.getPayments(token);
      setPayments(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <ScrollView style={styles.container}>
      <Button title="Record Payment" onPress={() => navigation.navigate('CreatePayment')} />
      <Text style={styles.heading}>Payments</Text>
      {payments.map(p => (
        <View key={p.id} style={styles.card}>
          <Text style={styles.amount}>KES {Number(p.amount).toLocaleString()}</Text>
          <Text>{p.church_name}</Text>
          <Text>{p.category_name}</Text>
          <Text>{p.payment_date}</Text>
          <Text>{p.notes}</Text>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  heading: { fontSize: 20, fontWeight: 'bold', marginVertical: 12 },
  card: { backgroundColor: '#f2f2f2', padding: 12, borderRadius: 8, marginBottom: 8 },
  amount: { fontWeight: 'bold', marginBottom: 4 },
});