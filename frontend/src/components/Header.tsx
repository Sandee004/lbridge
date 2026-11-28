import React from 'react';
import { ChevronDown, Download, Settings, UploadCloud } from 'lucide-react';
import type { BackendTransaction, WorkspacePage } from '../types';

interface HeaderProps {
  currentPage: WorkspacePage;
  onPageChange: (page: WorkspacePage) => void;
  onFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  isUploading: boolean;
  transactions: BackendTransaction[];
  activeStatementName?: string;
  activeStatementId?: string;
}

async function handleBackendExport(
  activeStatementId: string | undefined,
  format: 'csv' | 'xlsx',
  mode: 'flat' | 'journal' = 'flat'
): Promise<void> {
  if (!activeStatementId) {
    alert('Please select or upload a statement first.');
    return;
  }
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const res = await fetch(`/statements/${activeStatementId}/export?format=${format}&mode=${mode}`, {
      headers,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Export failed' }));
      alert(err.detail || 'Failed to export statement.');
      return;
    }

    const blob = await res.blob();
    const disposition = res.headers.get('content-disposition');
    let filename = `ledgerbridge_export.${format}`;
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename="?([^"]+)"?/);
      if (match && match[1]) {
        filename = match[1];
      }
    }

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    console.error('Export error:', err);
    alert('An error occurred during export.');
  }
}

export const Header: React.FC<HeaderProps> = ({
  currentPage,
  onPageChange,
  onFileUpload,
  isUploading,
  transactions,
  activeStatementName,
  activeStatementId,
}) => {
  const getPageInfo = (): { title: string; subtitle: string } => {
    switch (currentPage) {
      case 'overview':
        return {
          title: 'Financial Overview',
          subtitle: activeStatementName
            ? `Summary and element totals for ${activeStatementName}`
            : 'Consolidated balances across all uploaded statements',
        };
      case 'review':
        return {
          title: 'Review Queue',
          subtitle: 'Verify and map transactions that require human confirmation',
        };
      case 'ledger':
        return {
          title: 'General Ledger',
          subtitle: `${transactions.length} reconciled transactions across the 5 accounting elements`,
        };
      case 'rules':
        return {
          title: 'Categorization Rules',
          subtitle: 'Persistent pattern and keyword mappings saved for automatic processing',
        };
      case 'settings':
        return {
          title: 'Account Settings & Preferences',
          subtitle: 'Organization details, profile credentials, and export formatting',
        };
    }
  };

  const { title, subtitle } = getPageInfo();

  return (
    <header className="sticky top-0 z-30 flex min-h-[76px] py-4.5 items-center justify-between border-b border-slate-200 bg-white/95 px-8 backdrop-blur-sm shadow-2xs">
      {/* Page Title & Context */}
      <div className="space-y-0.5">
        <h2 className="text-lg font-bold text-slate-900 leading-tight">{title}</h2>
        <p className="text-xs text-slate-500 font-medium">{subtitle}</p>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3">
        {/* Export Dropdown */}
        <div className="relative group">
          <button className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition-colors">
            <Download className="h-3.5 w-3.5 text-slate-500" />
            <span>Export</span>
            <ChevronDown className="h-3 w-3 text-slate-400" />
          </button>
          <div className="absolute right-0 top-full mt-1 hidden w-56 rounded-xl border border-slate-200 bg-white p-1 shadow-lg group-hover:block z-50">
            <button
              onClick={() => handleBackendExport(activeStatementId, 'csv', 'flat')}
              className="w-full text-left rounded-lg px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 hover:text-emerald-700"
            >
              <p className="font-semibold">Clean Ledger (.CSV)</p>
              <p className="text-[10px] text-slate-400">Standard spreadsheet register</p>
            </button>
            <button
              onClick={() => handleBackendExport(activeStatementId, 'csv', 'journal')}
              className="w-full text-left rounded-lg px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 hover:text-emerald-700"
            >
              <p className="font-semibold">Double-Entry Journal (.CSV)</p>
              <p className="text-[10px] text-slate-400">Zoho Books & QuickBooks format</p>
            </button>
            <button
              onClick={() => handleBackendExport(activeStatementId, 'xlsx')}
              className="w-full text-left rounded-lg px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 hover:text-emerald-700"
            >
              <p className="font-semibold">Excel Audit Workbook (.XLSX)</p>
              <p className="text-[10px] text-slate-400">3 sheets with live SUMIFS formulas</p>
            </button>
          </div>
        </div>

        {/* Upload Statement Primary Button */}
        <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 transition-colors">
          <UploadCloud className="h-4 w-4" />
          <span>Upload Statement</span>
          <input
            type="file"
            accept=".pdf,.xlsx,.xls,.csv"
            onChange={onFileUpload}
            disabled={isUploading}
            className="hidden"
          />
        </label>

        {/* Profile / Settings Shortcut */}
        <button
          onClick={() => onPageChange('settings')}
          className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900 transition-colors"
          title="Settings"
        >
          <Settings className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
};
