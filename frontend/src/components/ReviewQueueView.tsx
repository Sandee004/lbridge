import React, { useState } from 'react';
import { CheckCircle2, ChevronRight, HelpCircle } from 'lucide-react';
import type { BackendTransaction, FinancialElement, WorkspacePage } from '../types';
import { ELEMENT_BADGE } from '../data/mockData';

interface ReviewQueueViewProps {
  pendingTransactions: BackendTransaction[];
  onResolve: (
    tx: BackendTransaction,
    element: Exclude<FinancialElement, 'Needs Review'>,
    saveRule: boolean
  ) => void;
  onNavigate: (page: WorkspacePage) => void;
  formatCurrency: (val?: number | null) => string;
}

const VALID_ELEMENTS: Exclude<FinancialElement, 'Needs Review'>[] = [
  'Assets',
  'Liabilities',
  'Income',
  'Expenses',
  'Capital',
];

export const ReviewQueueView: React.FC<ReviewQueueViewProps> = ({
  pendingTransactions,
  onResolve,
  onNavigate,
  formatCurrency,
}) => {
  const [saveRuleFlags, setSaveRuleFlags] = useState<Record<string, boolean>>({});

  if (pendingTransactions.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-12 text-center shadow-2xs">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
          <CheckCircle2 className="h-6 w-6" />
        </div>
        <h3 className="mt-4 text-base font-bold text-slate-900">Review Queue is Clear!</h3>
        <p className="mx-auto mt-1 max-w-sm text-xs text-slate-500 leading-relaxed">
          All bank statement transactions have been mapped across Assets, Liabilities, Income,
          Expenses, and Capital.
        </p>
        <button
          onClick={() => onNavigate('ledger')}
          className="mt-5 inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700 transition-colors shadow-2xs"
        >
          <span>Open General Ledger</span>
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Intro Context */}
      <div className="flex items-center justify-between text-xs text-slate-600 px-1">
        <p>
          <strong className="text-slate-900 font-bold">{pendingTransactions.length}</strong>{' '}
          transaction{pendingTransactions.length > 1 ? 's' : ''} require your categorization before closing the ledger.
        </p>
        <span className="text-[11px] text-slate-400">
          Click an element to confirm and save mapping
        </span>
      </div>

      {/* Review Queue Items List */}
      <div className="space-y-3">
        {pendingTransactions.map((tx) => {
          const shouldSaveRule = saveRuleFlags[tx.id] ?? true;
          const candidatePattern =
            tx.description_norm || tx.description_raw.split(/[-–—/]/)[0].trim().slice(0, 30);

          return (
            <div
              key={tx.id}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs transition-all hover:border-slate-300 hover:shadow-xs"
            >
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                {/* Transaction Information */}
                <div className="space-y-2 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-slate-500">{tx.date}</span>
                    <span
                      className={`font-mono text-xs font-bold px-2 py-0.5 rounded-md ${
                        tx.direction === 'credit'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-rose-50 text-rose-700 border border-rose-200'
                      }`}
                    >
                      {tx.direction === 'credit' ? '+' : '-'}
                      {formatCurrency(tx.amount)}
                    </span>
                    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-800 border border-amber-200">
                      Needs Review
                    </span>
                  </div>

                  <p className="font-medium text-slate-900 text-sm leading-snug">
                    {tx.description_raw}
                  </p>

                  {/* Clean finance explanation */}
                  {tx.reason && (
                    <div className="flex items-center gap-1.5 text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5">
                      <HelpCircle className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                      <span>{tx.reason}</span>
                    </div>
                  )}
                </div>

                {/* 1-Click Classification Buttons */}
                <div className="flex flex-wrap gap-1.5 sm:justify-end">
                  {VALID_ELEMENTS.map((elem) => {
                    const badge = ELEMENT_BADGE[elem];
                    return (
                      <button
                        key={elem}
                        onClick={() => onResolve(tx, elem, shouldSaveRule)}
                        className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all hover:scale-102 active:scale-98 ${badge.badge} hover:shadow-xs`}
                      >
                        <span className={`h-1.5 w-1.5 rounded-full ${badge.dot}`} />
                        <span>{elem}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Remember Rule Checkbox */}
              <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-xs text-slate-500">
                <label className="flex cursor-pointer items-center gap-2 select-none">
                  <input
                    type="checkbox"
                    checked={shouldSaveRule}
                    onChange={(e) =>
                      setSaveRuleFlags((prev) => ({ ...prev, [tx.id]: e.target.checked }))
                    }
                    className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                  />
                  <span>
                    Automatically categorize future transactions containing{' '}
                    <strong className="text-slate-700 font-semibold">"{candidatePattern}"</strong>
                  </span>
                </label>
                <span className="font-mono text-[10px] text-slate-400">
                  Ref: {tx.id.slice(0, 8)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
