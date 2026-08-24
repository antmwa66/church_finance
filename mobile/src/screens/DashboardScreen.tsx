import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { useAuth } from '../../context/AuthContext';

export default function DashboardScreen() {
  const { user } = useAuth();
  const stats = user?.stats || {};

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.heading}>{user?.full_name}</Text>
      <Text style={styles.subheading}>{user?.role?.replace('_', ' ').toUpperCase()}</Text>

      <View style={styles.grid}>
        {Object.entries(stats).map(([key, value]) => (
          <View key={key} style={styles.card}>
            <Text style={styles.cardLabel}>{key.replace(/_/g, ' ').toUpperCase()}</Text>
            <Text style={styles.cardValue}>
              {typeof value === 'number' && key.toLowerCase().includes('amount')
                ? `KES ${Number(value).toLocaleString()}`
                : String(value)}
            </Text>
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  heading: { fontSize: 22, fontWeight: 'bold' },
  subheading: { fontSize: 14, color: '#666', marginBottom: 16 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  card: { flex: 1, minWidth: '45%', backgroundColor: '#f2f2f2', padding: 16, borderRadius: 8 },
  cardLabel: { fontSize: 12, color: '#555', marginBottom: 4 },
  cardValue: { fontSize: 16, fontWeight: 'bold' },
});