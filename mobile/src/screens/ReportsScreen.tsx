import React, { useEffect, useState } from 'react';
import { View, Text, Button, StyleSheet, ScrollView } from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { api, ReportItem, Category } from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function ReportsScreen({ navigation }: any) {
  const { token } = useAuth();
  const [items, setItems] = useState<ReportItem[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryId, setCategoryId] = useState('');

  useEffect(() => {
    if (!token) return;
    Promise.all([api.getReports(token), api.getCategories(token)]).then(([reports, cats]) => {
      setItems(reports);
      setCategories(cats);
    });
  }, [token]);

  async function load() {
    if (!token) return;
    const reports = await api.getReports(token, categoryId ? Number(categoryId) : undefined);
    setItems(reports);
  }

  return (
    <ScrollView style={styles.container}>
      <View style={styles.filterRow}>
        <View style={styles.pickerContainer}>
          <Picker selectedValue={categoryId} onValueChange={setCategoryId}>
            <Picker.Item label="All Categories" value="" />
            {categories.map(c => (
              <Picker.Item key={c.id} label={c.name} value={String(c.id)} />
            ))}
          </Picker>
        </View>
        <Button title="Apply" onPress={load} />
      </View>

      {items.map((item, idx) => (
        <View key={idx} style={styles.card}>
          <Text style={styles.region}>{item.region_name}</Text>
          <Text>{item.sub_region_name}</Text>
          <Text>Allocation: KES {Number(item.allocation).toLocaleString()}</Text>
          <Text>Contributed: KES {Number(item.contributed).toLocaleString()}</Text>
          <Text>Balance: KES {Number(item.balance).toLocaleString()}</Text>
          <Text>Percentage: {item.percentage.toFixed(1)}%</Text>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  filterRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  pickerContainer: { flex: 1, borderWidth: 1, borderColor: '#ccc', borderRadius: 8 },
  card: { backgroundColor: '#f2f2f2', padding: 12, borderRadius: 8, marginBottom: 8 },
  region: { fontWeight: 'bold', fontSize: 16 },
});