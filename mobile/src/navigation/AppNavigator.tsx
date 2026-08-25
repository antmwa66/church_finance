import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../context/AuthContext';

import LoginScreen from '../screens/LoginScreen';
import DashboardScreen from '../screens/DashboardScreen';
import PaymentsScreen from '../screens/PaymentsScreen';
import CreatePaymentScreen from '../screens/CreatePaymentScreen';
import ChurchesScreen from '../screens/ChurchesScreen';
import CreateChurchScreen from '../screens/CreateChurchScreen';
import PastorsScreen from '../screens/PastorsScreen';
import CreatePastorScreen from '../screens/CreatePastorScreen';
import ReportsScreen from '../screens/ReportsScreen';
import ProfileScreen from '../screens/ProfileScreen';
import AuditScreen from '../screens/AuditScreen';
import NativeCppDemoScreen from '../screens/NativeCppDemoScreen';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

function MainTabs() {
  const { user } = useAuth();
  const role = user?.role;
  return (
    <Tab.Navigator screenOptions={({ route }) => ({
      tabBarIcon: ({ color, size }: { color: string; size: number }) => {
        let icon: keyof typeof Ionicons.glyphMap = 'home';
        if (route.name === 'Dashboard') icon = 'home';
        else if (route.name === 'Payments') icon = 'card';
        else if (route.name === 'Churches') icon = 'business';
        else if (route.name === 'Pastors') icon = 'people';
        else if (route.name === 'Reports') icon = 'bar-chart';
        else if (route.name === 'Audit') icon = 'search';
        else if (route.name === 'C++ Demo') icon = 'code-slash';
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
      {(role === 'admin' || role === 'regional_bishop') && (
        <Tab.Screen name="Audit" component={AuditScreen} />
      )}
      <Tab.Screen name="C++ Demo" component={NativeCppDemoScreen} />
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