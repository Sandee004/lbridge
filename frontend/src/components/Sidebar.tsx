import React, { useState } from 'react';
import {
  BookOpen,
  CheckSquare,
  FileSpreadsheet,
  FileText,
  LayoutDashboard,
  LogOut,
  PanelLeft,
  PanelLeftClose,
  Settings,
  SlidersHorizontal,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import type { BackendStatement, WorkspacePage } from '../types';

interface SidebarProps {
  currentPage: WorkspacePage;
  onPageChange: (page: WorkspacePage) => void;
  pendingCount: number;
  statements: BackendStatement[];
  selectedStatementId: string;
  onSelectStatement: (id: string) => void;
  onLoadSample: (type: 'access-bank-pdf' | 'demo-excel') => void;
  onLogout: () => void;
  userEmail: string;
  isUploading: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentPage,
  onPageChange,
  pendingCount,
  statements,
  selectedStatementId,
  onSelectStatement,
  onLoadSample,
  onLogout,
  userEmail,
  isUploading,
}) => {
  const [collapsed, setCollapsed] = useState<boolean>(false);

  const navItems: Array<{
    id: WorkspacePage;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    badge?: number;
  }> = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'review', label: 'Review Queue', icon: CheckSquare, badge: pendingCount },
    { id: 'ledger', label: 'General Ledger', icon: BookOpen },
    { id: 'rules', label: 'Mapping Rules', icon: SlidersHorizontal },
    { id: 'settings', label: 'Settings & Profile', icon: Settings },
  ];

  return (
    <aside
      className={`shrink-0 border-r border-slate-200 bg-white flex flex-col justify-between h-screen sticky top-0 transition-all duration-200 z-30 ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Brand & Statement Selector */}
      <div className="p-4 border-b border-slate-100">
        <div className="flex items-center justify-between">
          <Link
            to="/"
            className="flex items-center gap-2.5 hover:opacity-85 transition-opacity"
            title="Go to LedgerBridge Home"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 font-bold text-white shadow-xs shrink-0">
              LB
            </div>
            {!collapsed && (
              <div>
                <h1 className="text-sm font-bold tracking-tight text-slate-900 leading-none">
                  LedgerBridge
                </h1>
                <p className="mt-1 text-[11px] text-slate-500 font-medium">Reconciler</p>
              </div>
            )}
          </Link>

          {/* Minimize / Expand Toggle Button */}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
            title={collapsed ? 'Expand sidebar' : 'Minimize sidebar'}
          >
            {collapsed ? (
              <PanelLeft className="h-4 w-4" />
            ) : (
              <PanelLeftClose className="h-4 w-4" />
            )}
          </button>
        </div>

        {/* Statement Switcher */}
        {!collapsed ? (
          <div className="mt-4">
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
              Active Statement
            </label>
            <select
              value={selectedStatementId}
              onChange={(e) => onSelectStatement(e.target.value)}
              className="w-full truncate rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-medium text-slate-700 focus:border-emerald-500 focus:bg-white focus:outline-none"
            >
              <option value="all">Consolidated (All Statements)</option>
              {statements.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.bank_name} ({s.transaction_count} txns)
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="mt-3 flex justify-center">
            <span
              className="h-2 w-2 rounded-full bg-emerald-500"
              title={`Active: ${statements.length} statement(s)`}
            />
          </div>
        )}
      </div>

      {/* Main Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentPage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onPageChange(item.id)}
              className={`relative w-full flex items-center rounded-lg px-3 py-2.5 text-xs font-semibold transition-all ${
                collapsed ? 'justify-center px-0' : 'justify-between'
              } ${
                isActive
                  ? 'bg-emerald-50 text-emerald-800 font-bold shadow-xs'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
              title={collapsed ? `${item.label}${item.badge ? ` (${item.badge})` : ''}` : undefined}
            >
              <div className="relative flex items-center gap-2.5">
                <Icon
                  className={`h-4 w-4 shrink-0 ${
                    isActive ? 'text-emerald-600' : 'text-slate-400'
                  }`}
                />
                {collapsed && item.badge !== undefined && item.badge > 0 && (
                  <span
                    className="absolute -top-1 -right-1 h-2 w-2 rounded-full bg-amber-500 ring-2 ring-white"
                    title={`${item.badge} pending review`}
                  />
                )}
                {!collapsed && <span>{item.label}</span>}
              </div>
              {!collapsed && item.badge !== undefined && item.badge > 0 && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-mono font-bold text-amber-800 border border-amber-200">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Bottom Samples & User Area */}
      <div className="p-3 border-t border-slate-100 space-y-2">
        {/* Sample Loaders */}
        {!collapsed && (
          <div className="rounded-lg bg-slate-50 p-2.5 border border-slate-200/80">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
              Quick Sample Statements
            </p>
            <div className="grid grid-cols-2 gap-1.5">
              <button
                onClick={() => onLoadSample('access-bank-pdf')}
                disabled={isUploading}
                className="flex items-center justify-center gap-1 rounded border border-slate-200 bg-white px-2 py-1.5 text-[11px] font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                title="Load Access Bank sample statement (PDF)"
              >
                <FileText className="h-3 w-3 text-emerald-600" />
                <span>Bank PDF</span>
              </button>
              <button
                onClick={() => onLoadSample('demo-excel')}
                disabled={isUploading}
                className="flex items-center justify-center gap-1 rounded border border-slate-200 bg-white px-2 py-1.5 text-[11px] font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                title="Load Corporate Excel statement (.xlsx)"
              >
                <FileSpreadsheet className="h-3 w-3 text-emerald-600" />
                <span>Excel</span>
              </button>
            </div>
          </div>
        )}

        {/* User Profile Bar */}
        <div
          className={`flex items-center pt-1 px-1 ${
            collapsed ? 'justify-center flex-col gap-2' : 'justify-between'
          }`}
        >
          <button
            onClick={() => onPageChange('settings')}
            className={`flex items-center gap-2 text-left hover:opacity-80 transition-opacity truncate ${
              collapsed ? 'justify-center' : 'max-w-[170px]'
            }`}
            title={userEmail}
          >
            <div className="h-7 w-7 rounded-full bg-slate-200 text-slate-700 font-bold text-xs flex items-center justify-center shrink-0">
              {userEmail.charAt(0).toUpperCase()}
            </div>
            {!collapsed && (
              <div className="truncate">
                <p className="text-xs font-semibold text-slate-900 truncate">
                  {userEmail.split('@')[0]}
                </p>
                <p className="text-[10px] text-slate-400 truncate">{userEmail}</p>
              </div>
            )}
          </button>
          <button
            onClick={onLogout}
            className="p-1.5 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
            title="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};
