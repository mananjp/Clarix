import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';

// Layouts
import MainLayout from './layouts/MainLayout';
import AuthLayout from './layouts/AuthLayout';

// Auth Pages
import Login from './pages/Login';
import Signup from './pages/Signup';

// Protected Pages
import Dashboard from './pages/Dashboard';
import RequirementMatrix from './pages/RequirementMatrix';
import ReviewerDesk from './pages/ReviewerDesk';
import AuditTrail from './pages/AuditTrail';
import Settings from './pages/Settings';

const ProtectedRoute = () => {
  const { currentUser, loading } = useAuth();
  
  if (loading) return <div className="h-screen w-screen flex items-center justify-center bg-slate-50 text-slate-500">Loading workspace...</div>;
  
  return currentUser ? <Outlet /> : <Navigate to="/login" replace />;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Auth Routes */}
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
          </Route>

          {/* Protected App Routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<MainLayout />}>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="matrix" element={<RequirementMatrix />} />
              <Route path="reviewer" element={<ReviewerDesk />} />
              <Route path="audit" element={<AuditTrail />} />
              <Route path="settings" element={<Settings />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
