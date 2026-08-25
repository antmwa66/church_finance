import React from 'react';
import { ErrorBoundary } from './src/components/ErrorBoundary';
import { AuthProvider } from './src/context/AuthContext';
import AppNavigator from './src/navigation/AppNavigator';

if (typeof global.DOMRect === 'undefined') {
  class DOMRect {
    x = 0;
    y = 0;
    width = 0;
    height = 0;
    top = 0;
    left = 0;
    bottom = 0;
    right = 0;
    constructor(x = 0, y = 0, width = 0, height = 0) {
      this.x = x; this.y = y; this.width = width; this.height = height;
      this.top = y; this.left = x; this.bottom = y + height; this.right = x + width;
    }
    toJSON() { return {}; }
  }
  (global as any).DOMRect = DOMRect;
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <AppNavigator />
      </AuthProvider>
    </ErrorBoundary>
  );
}