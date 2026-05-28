import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import Dashboard from './pages/Dashboard';
import RequirementMatrix from './pages/RequirementMatrix';
import ReviewerDesk from './pages/ReviewerDesk';
import AuditTrail from './pages/AuditTrail';
import Settings from './pages/Settings';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="matrix" element={<RequirementMatrix />} />
          <Route path="reviewer" element={<ReviewerDesk />} />
          <Route path="audit" element={<AuditTrail />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
