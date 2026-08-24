import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../src/context/AuthContext';

import LoginScreen from '../src/screens/LoginScreen';
import DashboardScreen from '../src/screens/DashboardScreen';
import PaymentsScreen from '../src/screens/PaymentsScreen';
import CreatePaymentScreen from '../src/screens/CreatePaymentScreen';
import ChurchesScreen from '../src/screens/ChurchesScreen';
import CreateChurchScreen from '../src/screens/CreateChurchScreen';
import PastorsScreen from '../src/screens/PastorsScreen';
import CreatePastorScreen from '../src/screens/CreatePastorScreen';
import ReportsScreen from '../src/screens/ReportsScreen';
import ProfileScreen from '../src/screens/ProfileScreen';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

function MainTabs() {
  return (
    <Tab.Navigator screenOptions={({ route }) => ({
      tabBarIcon: ({ color, size }: { color: string; size: number }) => {
        let icon: keyof typeof Ionicons.glyphMap = 'home';
        if (route.name === 'Dashboard') icon = 'home';
        else if (route.name === 'Payments') icon = 'card';
        else if (route.name === 'Churches') icon = 'business';
        else if (route.name === 'Pastors') icon = 'people';
        else if (route.name === 'Reports') icon = 'bar-chart';
        else if (route.name === 'Profile') icon = 'person';
        return <Ionicons name={icon} size={size} color={color} />;
      },
      tabBarActiveTintColor: '#2c3e50',
      headerShown: false,
    })}>
      <Tab.Screen name="Dashboard" component={DashboardScreen} />
      <Tab.Screen name="Payments" component={PaymentsScreen} />
      <Tab.Screen name="Churches" component={ChurchesScreen} />
      <Tab.Screen name="Pastors" component={PastorsScreen} />
      <Tab.Screen name="Reports" component={ReportsScreen} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}

export default function AppNavigator() {
  const { loading, user } = useAuth();

  if (loading) return null;

  return (
    <NavigationContainer>
      <Stack.Navigator>
        {!user ? (
          <Stack.Screen name="Login" component={LoginScreen} options={{ headerShown: false }} />
        ) : (
          <>
            <Stack.Screen name="Main" component={MainTabs} options={{ headerShown: false }} />
            <Stack.Screen name="CreatePayment" component={CreatePaymentScreen} options={{ title: 'Record Payment' }} />
            <Stack.Screen name="CreateChurch" component={CreateChurchScreen} options={{ title: 'Add Church' }} />
            <Stack.Screen name="CreatePastor" component={CreatePastorScreen} options={{ title: 'Add Pastor' }} />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}