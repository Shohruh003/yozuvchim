import { Routes, Route, Navigate } from 'react-router-dom';

import { Layout } from '@/components/Layout';
import { AdminLayout } from '@/components/AdminLayout';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { AdminGuard } from '@/components/AdminGuard';

import LoginPage from '@/pages/LoginPage';
import ProfilePage from '@/pages/ProfilePage';
import OrdersPage from '@/pages/OrdersPage';
import NewOrderPage from '@/pages/NewOrderPage';
import OrderDetailPage from '@/pages/OrderDetailPage';
import PaymentsPage from '@/pages/PaymentsPage';

import AdminDashboardPage from '@/pages/admin/AdminDashboardPage';
import AdminUsersPage from '@/pages/admin/AdminUsersPage';
import AdminPaymentsPage from '@/pages/admin/AdminPaymentsPage';
import AdminLoginPage from '@/pages/admin/AdminLoginPage';
import AdminTransactionsPage from '@/pages/admin/AdminTransactionsPage';
import AdminCardsPage from '@/pages/admin/AdminCardsPage';
import AdminAdminsPage from '@/pages/admin/AdminAdminsPage';
import AdminSettingsPage from '@/pages/admin/AdminSettingsPage';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/admin/login" element={<AdminLoginPage />} />

      {/* User app */}
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/" element={<Navigate to="/profile" replace />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/orders/new" element={<NewOrderPage />} />
        <Route path="/orders/:id" element={<OrderDetailPage />} />
        <Route path="/payments" element={<PaymentsPage />} />
      </Route>

      {/* Admin app */}
      <Route element={<AdminGuard><AdminLayout /></AdminGuard>}>
        <Route path="/admin" element={<AdminDashboardPage />} />
        <Route path="/admin/users" element={<AdminUsersPage />} />
        <Route path="/admin/payments" element={<AdminPaymentsPage />} />
        <Route path="/admin/transactions" element={<AdminTransactionsPage />} />
        <Route path="/admin/cards" element={<AdminCardsPage />} />
        <Route path="/admin/admins" element={<AdminAdminsPage />} />
        <Route path="/admin/settings" element={<AdminSettingsPage />} />
      </Route>
    </Routes>
  );
}
