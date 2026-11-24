import React, { useState } from 'react';
import { ArrowLeft, Lock, RefreshCw } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { PasswordInput } from './PasswordInput';

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : window.location.port === '5173'
    ? ''
    : 'http://127.0.0.1:8000';

interface AuthViewProps {
  initialMode?: 'login' | 'signup';
}

export const AuthView: React.FC<AuthViewProps> = ({ initialMode = 'login' }) => {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'signup'>(initialMode);
  const [email, setEmail] = useState('finance@company.com');
  const [password, setPassword] = useState('SecurePassword123!');
  const [companyName, setCompanyName] = useState('Acme Finance Ltd');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const endpoint = mode === 'signup' ? `${BASE_URL}/auth/signup` : `${BASE_URL}/auth/login`;
      const payload =
        mode === 'signup'
          ? { email, password, company_name: companyName }
          : { email, password };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include', // Sends & receives HttpOnly cookie!
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: 'Authentication failed' }));
        throw new Error(data.detail || 'Authentication failed');
      }

      const data = await res.json();
      if (data.user) {
        localStorage.setItem('lb_user', JSON.stringify(data.user));
      }
      navigate('/workspace/overview');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Authentication failed. Please check your details.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 font-sans text-slate-900 selection:bg-emerald-100 selection:text-emerald-900">
      {/* Top Header */}
      <header className="flex h-18 items-center justify-between border-b border-slate-200 bg-white px-8">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back to overview
        </Link>
        <span className="text-xs font-semibold text-slate-400">LedgerBridge Reconciler</span>
      </header>

      {/* Main Form Card */}
      <div className="flex flex-1 items-center justify-center px-6 py-16">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-600 font-bold text-sm text-white shadow-xs">
              LB
            </span>
            <Lock className="h-4 w-4 text-slate-400" />
          </div>

          <h1 className="mt-5 text-xl font-bold tracking-tight text-slate-900">
            {mode === 'login' ? 'Sign in to LedgerBridge' : 'Set up your company workspace'}
          </h1>
          <p className="mt-1 text-xs text-slate-500 leading-relaxed">
            {mode === 'login'
              ? 'Access your bank statements, general ledger, and reconciliation queue.'
              : 'Create a private, offline accounting workspace on this computer.'}
          </p>

          {error && (
            <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            {mode === 'signup' && (
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Company / Organization Name
                </label>
                <input
                  type="text"
                  required
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="e.g. Acme Operations Ltd"
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 focus:border-emerald-500 focus:bg-white focus:outline-none"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Work Email Address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="finance@company.com"
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 focus:border-emerald-500 focus:bg-white focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Password
              </label>
              <PasswordInput
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                required
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 rounded-lg bg-emerald-600 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-emerald-700 disabled:opacity-50 transition-colors"
            >
              {isLoading && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
              <span>{mode === 'login' ? 'Open Workspace' : 'Create Workspace'}</span>
            </button>
          </form>

          <div className="mt-6 border-t border-slate-100 pt-4 text-center">
            <button
              type="button"
              onClick={() => {
                setError(null);
                setMode(mode === 'login' ? 'signup' : 'login');
              }}
              className="text-xs text-slate-500 hover:text-emerald-700 transition-colors font-medium"
            >
              {mode === 'login'
                ? "Don't have a workspace yet? Create one"
                : 'Already have an existing workspace? Sign in'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
