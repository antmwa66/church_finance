import React, { useEffect, useState } from 'react';
import { View, Text, Button, StyleSheet, ScrollView } from 'react-native';
import { api, Church } from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function ChurchesScreen({ navigation }: any) {
  const { token } = useAuth();
  const [churches, setChurches] = useState<Church[]>([]);

  useEffect(() => {
    if (!token) return;
    api.getChurches(token).then(setChurches);
  }, [token]);

  return (
    <ScrollView style={styles.container}>
      <Button title="Add Church" onPress={() => navigation.navigate('CreateChurch')} />
      {churches.map(c => (
        <View key={c.id} style={styles.card}>
          <Text style={styles.name}>{c.name}</Text>
          <Text>{c.is_active ? 'Active' : 'Inactive'}</Text>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  card: { backgroundColor: '#f2f2f2', padding: 12, borderRadius: 8, marginTop: 8 },
  name: { fontWeight: 'bold', fontSize: 16 },
});