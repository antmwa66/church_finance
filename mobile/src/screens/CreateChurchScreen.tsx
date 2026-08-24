import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, Button, StyleSheet, ScrollView } from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { api, Church } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

export default function CreateChurchScreen({ navigation }: any) {
  const { token } = useAuth();
  const [subRegions, setSubRegions] = useState<any[]>([]);
  const [name, setName] = useState('');
  const [subRegionId, setSubRegionId] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!token) return;
    api.getSubRegions(token).then(setSubRegions);
  }, [token]);

  async function submit() {
    if (!token || !name || !subRegionId) return;
    setSaving(true);
    try {
      await api.createChurch(token, { name, sub_region_id: Number(subRegionId) });
      navigation.goBack();
    } finally {
      setSaving(false);
    }
  }

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.label}>Church Name</Text>
      <TextInput style={styles.input} value={name} onChangeText={setName} />

      <Text style={styles.label}>Sub-Region</Text>
      <View style={styles.pickerContainer}>
        <Picker selectedValue={subRegionId} onValueChange={setSubRegionId}>
          <Picker.Item label="Select sub-region" value="" />
          {subRegions.map(sr => (
            <Picker.Item key={sr.id} label={sr.name} value={String(sr.id)} />
          ))}
        </Picker>
      </View>

      <Button title={saving ? 'Saving...' : 'Create Church'} onPress={submit} disabled={saving} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  label: { marginTop: 12, fontWeight: 'bold' },
  input: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 12, marginTop: 4 },
  pickerContainer: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, marginTop: 4, marginBottom: 12 },
});