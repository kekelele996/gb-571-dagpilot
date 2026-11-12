import { Navigate, Route, Routes } from 'react-router-dom';
import AppShell from '../components/layout/AppShell';
import Jobs from '../pages/Jobs';
import Login from '../pages/Login';
import Simulate from '../pages/Simulate';
import Sla from '../pages/Sla';
import Watch from '../pages/Watch';
import { RequireAuth, RequirePermission } from './guards';

function Protected({ permission, children }: { permission: string; children: React.ReactNode }) {
  return (
    <RequireAuth>
      <AppShell>
        <RequirePermission permission={permission}>{children}</RequirePermission>
      </AppShell>
    </RequireAuth>
  );
}

export default function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Navigate to="/jobs" replace />} />
      <Route
        path="/jobs"
        element={
          <Protected permission="dag:validate">
            <Jobs />
          </Protected>
        }
      />
      <Route
        path="/simulate"
        element={
          <Protected permission="run:simulate">
            <Simulate />
          </Protected>
        }
      />
      <Route
        path="/sla"
        element={
          <Protected permission="backfill:read">
            <Sla />
          </Protected>
        }
      />
      <Route
        path="/watch"
        element={
          <Protected permission="estimate:read">
            <Watch />
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to="/jobs" replace />} />
    </Routes>
  );
}
