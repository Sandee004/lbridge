import React from 'react';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Scale,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import type { BackendStatement, FinancialElement, WorkspacePage } from '../types';
import { ELEMENT_BADGE } from '../data/mockData';

interface OverviewViewProps {
  activeStatement: BackendStatement | null;
  elementTotals: Record<Exclude<FinancialElement, 'Needs Review'>, number> & {
    totalCredits: number;
    totalDebits: number;
    netFlow: number;
  };
  pendingCount: number;
  onNavigate: (page: WorkspacePage) => void;
  onFilterElement: (elem: FinancialElement) => void;
  formatCurrency: (val?: number | null) => string;
}

const VALID_ELEMENTS: Exclude<FinancialElement, 'Needs Review'>[] = [
  'Assets',
  'Liabilities',
  'Income',
  'Expenses',
  'Capital',
];

export const OverviewView: React.FC<OverviewViewProps> = ({
  activeStatement,
  elementTotals,
  pendingCount,
  onNavigate,
  onFilterElement,
  formatCurrency,
}) => {
  return (
    <div className="space-y-6">
      {/* Pending Triage Banner (if items exist) */}
      {pendingCount > 0 && (
        <div className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50/70 p-4 shadow-2xs">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-100 text-amber-800">
              <Scale className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-amber-900">
                {pendingCount} Transaction{pendingCount > 1 ? 's' : ''} Need Review
              </h3>
              <p className="text-[11px] text-amber-700">
                Some transactions have ambiguous descriptions or require confirmation before closing the ledger.
              </p>
            </div>
          </div>
          <button
            onClick={() => onNavigate('review')}
            className="inline-flex items-center gap-1.5 rounded-lg bg-amber-800 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-amber-900 transition-colors"
          >
            <span>Review Now</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Statement Reconciliation Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-4">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Bank Statement Context
            </span>
            <h3 className="text-base font-bold text-slate-900 mt-0.5">
              {activeStatement ? activeStatement.bank_name : 'All Bank Statements (Consolidated)'}
            </h3>
            {activeStatement?.period_start && activeStatement?.period_end && (
              <p className="text-xs text-slate-500 mt-0.5">
                Statement Period: {activeStatement.period_start} – {activeStatement.period_end}
              </p>
            )}
          </div>

          {/* Statement Reconciliation Status in Plain English */}
          {activeStatement && (
            <div
              className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium border ${
                activeStatement.math_ok
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                  : 'border-amber-200 bg-amber-50 text-amber-800'
              }`}
            >
              {activeStatement.math_ok ? (
                <>
                  <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                  <span>Statement Arithmetic Balanced</span>
                </>
              ) : (
                <>
                  <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                  <span>
                    Discrepancy: {activeStatement.math_error_detail || 'Opening + Inflows - Outflows ≠ Closing'}
                  </span>
                </>
              )}
            </div>
          )}
        </div>

        {/* 4 Core Financial Totals */}
        <div className="grid grid-cols-2 gap-4 pt-4 sm:grid-cols-4">
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase">Opening Balance</p>
            <p className="mt-1 font-mono text-base font-bold text-slate-900 tabular-nums">
              {formatCurrency(activeStatement?.opening_balance)}
            </p>
          </div>
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase flex items-center gap-1">
              <TrendingUp className="h-3 w-3 text-emerald-600" />
              Total Inflows (Credits)
            </p>
            <p className="mt-1 font-mono text-base font-bold text-emerald-700 tabular-nums">
              +{formatCurrency(elementTotals.totalCredits)}
            </p>
          </div>
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase flex items-center gap-1">
              <TrendingDown className="h-3 w-3 text-rose-600" />
              Total Outflows (Debits)
            </p>
            <p className="mt-1 font-mono text-base font-bold text-rose-700 tabular-nums">
              -{formatCurrency(elementTotals.totalDebits)}
            </p>
          </div>
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase">Closing Balance</p>
            <p className="mt-1 font-mono text-base font-bold text-slate-900 tabular-nums">
              {formatCurrency(activeStatement?.closing_balance)}
            </p>
          </div>
        </div>
      </div>

      {/* 5 Financial Elements Breakdown */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900">5 Financial Elements Distribution</h3>
            <p className="text-xs text-slate-500">
              Categorized according to standard financial accounting standards
            </p>
          </div>
          <button
            onClick={() => onNavigate('ledger')}
            className="text-xs font-semibold text-emerald-700 hover:text-emerald-800 transition-colors flex items-center gap-1"
          >
            <span>View Full Ledger</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {VALID_ELEMENTS.map((elem) => {
            const badge = ELEMENT_BADGE[elem];
            const amount = elementTotals[elem];
            return (
              <div
                key={elem}
                onClick={() => {
                  onFilterElement(elem);
                  onNavigate('ledger');
                }}
                className="cursor-pointer rounded-xl border border-slate-200 bg-white p-4 shadow-2xs hover:border-slate-300 hover:shadow-xs transition-all flex flex-col justify-between"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-800">{elem}</span>
                  <span className={`h-2.5 w-2.5 rounded-full ${badge.dot}`} />
                </div>
                <div className="mt-3">
                  <p className="font-mono text-lg font-bold text-slate-900 tabular-nums">
                    {formatCurrency(amount)}
                  </p>
                  <p className="mt-1 text-[11px] text-slate-400 font-medium">Click to inspect rows</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Net Position / Cashflow Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Net Cash Flow Position
          </h4>
          <p className="mt-1 text-xs text-slate-600">
            Net difference between statement deposits and disbursements during this period
          </p>
        </div>
        <div className="text-right">
          <p
            className={`font-mono text-xl font-bold tabular-nums ${
              elementTotals.netFlow >= 0 ? 'text-emerald-700' : 'text-rose-700'
            }`}
          >
            {elementTotals.netFlow >= 0 ? '+' : ''}
            {formatCurrency(elementTotals.netFlow)}
          </p>
          <p className="text-[11px] text-slate-400">Total Credits minus Total Debits</p>
        </div>
      </div>
    </div>
  );
};
