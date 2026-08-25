import React, { useState } from 'react';
import { View, Text, TextInput, Button, StyleSheet, ScrollView, Alert } from 'react-native';
import { NativeCpp } from '../../modules/NativeCppModule';

export default function NativeCppDemoScreen() {
  const [input, setInput] = useState('');
  const [reversed, setReversed] = useState('');
  const [contributed, setContributed] = useState('0');
  const [allocation, setAllocation] = useState('0');
  const [percentage, setPercentage] = useState<number | null>(null);
  const [amount, setAmount] = useState('0');
  const [formatted, setFormatted] = useState('');

  async function testReverse() {
    if (!input.trim()) return;
    const result = await NativeCpp.reverseString(input.trim());
    setReversed(result);
  }

  async function testPercentage() {
    const c = parseFloat(contributed);
    const a = parseFloat(allocation);
    if (isNaN(c) || isNaN(a)) {
      Alert.alert('Error', 'Enter valid numbers');
      return;
    }
    const result = await NativeCpp.computePercentage(c, a);
    setPercentage(result);
  }

  async function testFormatKES() {
    const val = parseFloat(amount);
    if (isNaN(val)) {
      Alert.alert('Error', 'Enter a valid amount');
      return;
    }
    const result = await NativeCpp.formatKES(val);
    setFormatted(result);
  }

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.heading}>C++ NDK Module Demo</Text>

      <View style={styles.card}>
        <Text style={styles.label}>Reverse String (C++)</Text>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder="Type something..."
        />
        <Button title="Reverse" onPress={testReverse} />
        {reversed ? <Text style={styles.result}>Result: {reversed}</Text> : null}
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Compute Percentage (C++)</Text>
        <TextInput
          style={styles.input}
          keyboardType="numeric"
          value={contributed}
          onChangeText={setContributed}
          placeholder="Contributed"
        />
        <TextInput
          style={styles.input}
          keyboardType="numeric"
          value={allocation}
          onChangeText={setAllocation}
          placeholder="Allocation"
        />
        <Button title="Calculate" onPress={testPercentage} />
        {percentage !== null ? (
          <Text style={styles.result}>Percentage: {percentage.toFixed(2)}%</Text>
        ) : null}
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Format KES (C++)</Text>
        <TextInput
          style={styles.input}
          keyboardType="numeric"
          value={amount}
          onChangeText={setAmount}
          placeholder="Amount"
        />
        <Button title="Format" onPress={testFormatKES} />
        {formatted ? <Text style={styles.result}>Result: {formatted}</Text> : null}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  heading: { fontSize: 22, fontWeight: 'bold', marginBottom: 16 },
  card: { backgroundColor: '#f2f2f2', padding: 16, borderRadius: 8, marginBottom: 16 },
  label: { fontWeight: 'bold', marginBottom: 8 },
  input: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 12, marginBottom: 12 },
  result: { marginTop: 12, fontSize: 16, fontWeight: 'bold', color: '#2c3e50' },
});