import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { LandingPage } from './components/LandingPage';
import { AuthView } from './components/AuthView';
import { Workspace } from './components/Workspace';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<AuthView initialMode="login" />} />
        <Route path="/signup" element={<AuthView initialMode="signup" />} />
        <Route path="/workspace" element={<Navigate to="/workspace/overview" replace />} />
        <Route path="/workspace/:page" element={<Workspace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
