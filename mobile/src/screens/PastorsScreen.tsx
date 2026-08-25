import React, { useEffect, useState } from 'react';
import { View, Text, Button, StyleSheet, ScrollView } from 'react-native';
import { api, Pastor } from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function PastorsScreen({ navigation }: any) {
  const { token } = useAuth();
  const [pastors, setPastors] = useState<Pastor[]>([]);

  useEffect(() => {
    if (!token) return;
    api.getPastors(token).then(setPastors);
  }, [token]);

  return (
    <ScrollView style={styles.container}>
      <Button title="Add Pastor" onPress={() => navigation.navigate('CreatePastor')} />
      {pastors.map(p => (
        <View key={p.id} style={styles.card}>
          <Text style={styles.name}>{p.full_name}</Text>
          <Text>{p.church_name}</Text>
          <Text>{p.email}</Text>
          <Text>{p.phone}</Text>
          <Text>{p.is_active ? 'Active' : 'Inactive'}</Text>
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