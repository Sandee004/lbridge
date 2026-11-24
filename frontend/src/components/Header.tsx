import React from 'react';
import { ChevronDown, Download, Settings, UploadCloud } from 'lucide-react';
import type { BackendTransaction, WorkspacePage } from '../types';
import { normalizeElement } from '../types';

interface HeaderProps {
  currentPage: WorkspacePage;
  onPageChange: (page: WorkspacePage) => void;
  onFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  isUploading: boolean;
  transactions: BackendTransaction[];
  activeStatementName?: string;
}

function exportTransactionsCSV(
  transactions: BackendTransaction[],
  mode: 'flat' | 'journal',
  filenamePrefix: string = 'ledgerbridge'
): void {
  const csvRows: string[] = [];

  if (mode === 'flat') {
    csvRows.push('ID,Date,Value_Date,Narration,Direction,Amount,Element,Tier,Confidence,Status');
    transactions.forEach((t) => {
      const cleanDesc = (t.description_raw || '').replace(/"/g, '""');
      const elem = normalizeElement(t.element);
      csvRows.push(
        `"${t.id}","${t.date}","${t.value_date || t.date}","${cleanDesc}","${t.direction}",${t.amount},"${elem}","${t.tier || 'auto'}",${t.confidence ?? 1.0},"${t.status || 'auto'}"`
      );
    });
  } else {
    // Balanced Double-Entry Journal for Accounting software (Zoho Books, QuickBooks format)
    csvRows.push('Journal_Date,Journal_Number,Account_Name,Debit,Credit,Description');
    transactions.forEach((t) => {
      const cleanDesc = (t.description_raw || '').replace(/"/g, '""');
      const elem = normalizeElement(t.element);
      const jrnId = `JRN-${t.id.slice(0, 8).toUpperCase()}`;

      if (t.direction === 'credit') {
        csvRows.push(`"${t.date}","${jrnId}","Bank Account",${t.amount},0,"${cleanDesc}"`);
        csvRows.push(`"${t.date}","${jrnId}","${elem}",0,${t.amount},"${cleanDesc}"`);
      } else {
        csvRows.push(`"${t.date}","${jrnId}","${elem}",${t.amount},0,"${cleanDesc}"`);
        csvRows.push(`"${t.date}","${jrnId}","Bank Account",0,${t.amount},"${cleanDesc}"`);
      }
    });
  }

  const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${filenamePrefix}_${mode === 'flat' ? 'clean_ledger' : 'double_entry_journal'}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export const Header: React.FC<HeaderProps> = ({
  currentPage,
  onPageChange,
  onFileUpload,
  isUploading,
  transactions,
  activeStatementName,
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
          <div className="absolute right-0 top-full mt-1 hidden w-52 rounded-xl border border-slate-200 bg-white p-1 shadow-lg group-hover:block z-50">
            <button
              onClick={() => exportTransactionsCSV(transactions, 'flat')}
              className="w-full text-left rounded-lg px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 hover:text-emerald-700"
            >
              <p className="font-semibold">Clean Ledger (.CSV)</p>
              <p className="text-[10px] text-slate-400">Standard spreadsheet format</p>
            </button>
            <button
              onClick={() => exportTransactionsCSV(transactions, 'journal')}
              className="w-full text-left rounded-lg px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 hover:text-emerald-700"
            >
              <p className="font-semibold">Double-Entry Journal (.CSV)</p>
              <p className="text-[10px] text-slate-400">Zoho Books & QuickBooks format</p>
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
