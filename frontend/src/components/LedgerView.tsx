import React, { useMemo, useState } from 'react';
import { ChevronDown, Search } from 'lucide-react';
import type { BackendTransaction, FinancialElement } from '../types';
import { normalizeElement } from '../types';
import { ELEMENT_BADGE } from '../data/mockData';

interface LedgerViewProps {
  transactions: BackendTransaction[];
  onReclassify: (txnId: string, element: FinancialElement) => void;
  formatCurrency: (val?: number | null) => string;
  initialElementFilter?: string;
}

const VALID_ELEMENTS: FinancialElement[] = [
  'Assets',
  'Liabilities',
  'Income',
  'Expenses',
  'Capital',
  'Needs Review',
];

export const LedgerView: React.FC<LedgerViewProps> = ({
  transactions,
  onReclassify,
  formatCurrency,
  initialElementFilter = 'All',
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [elementFilter, setElementFilter] = useState<string>(initialElementFilter);

  const filteredTransactions = useMemo(() => {
    return transactions.filter((t) => {
      const normalizedElem = normalizeElement(t.element);
      const matchesElement = elementFilter === 'All' || normalizedElem === elementFilter;
      const matchesSearch =
        t.description_raw.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.amount.toString().includes(searchQuery) ||
        t.date.includes(searchQuery);
      return matchesElement && matchesSearch;
    });
  }, [transactions, elementFilter, searchQuery]);

  return (
    <div className="space-y-4">
      {/* Search and Filters Toolbar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-slate-200 bg-white p-3.5 shadow-2xs">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search transactions by narration, counterparty, amount..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-10 pr-4 text-xs text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:bg-white focus:outline-none"
          />
        </div>

        {/* Element Filter Pills */}
        <div className="flex flex-wrap items-center gap-1.5">
          {['All', ...VALID_ELEMENTS].map((elem) => (
            <button
              key={elem}
              onClick={() => setElementFilter(elem)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                elementFilter === elem
                  ? 'bg-slate-900 text-white shadow-2xs'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              {elem}
            </button>
          ))}
        </div>
      </div>

      {/* Transactions Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-2xs">
        <table className="w-full border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50/80 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Description / Counterparty</th>
              <th className="px-4 py-3 text-right">Amount</th>
              <th className="px-4 py-3">Accounting Category</th>
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3 text-right">Balance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredTransactions.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-12 text-center text-slate-400">
                  No transactions match your search or filter criteria.
                </td>
              </tr>
            ) : (
              filteredTransactions.map((t) => {
                const displayElem = normalizeElement(t.element);
                const badge = ELEMENT_BADGE[displayElem];

                // Simple finance source label: 'Rule', 'AI', or 'Manual'
                let sourceLabel = 'Rule';
                let sourceStyle = 'bg-slate-100 text-slate-700 border-slate-200';
                if (t.tier === 'llm') {
                  sourceLabel = 'AI';
                  sourceStyle = 'bg-emerald-50 text-emerald-700 border-emerald-200';
                } else if (t.tier === 'user') {
                  sourceLabel = 'Manual';
                  sourceStyle = 'bg-sky-50 text-sky-700 border-sky-200';
                }

                return (
                  <tr key={t.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-4 py-3 font-mono text-slate-600 whitespace-nowrap">
                      {t.date}
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-slate-900 leading-snug">
                        {t.description_raw}
                      </p>
                      {t.reason && (
                        <p className="mt-0.5 text-[10px] text-slate-400 truncate max-w-md">
                          {t.reason}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <span
                        className={`font-mono font-bold tabular-nums ${
                          t.direction === 'credit' ? 'text-emerald-700' : 'text-rose-700'
                        }`}
                      >
                        {t.direction === 'credit' ? '+' : '-'}
                        {formatCurrency(t.amount)}
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="relative inline-block">
                        <select
                          value={displayElem}
                          onChange={(e) =>
                            onReclassify(t.id, e.target.value as FinancialElement)
                          }
                          className={`appearance-none cursor-pointer rounded-full px-2.5 py-0.5 pr-6 text-xs font-semibold border ${badge.badge} focus:outline-none focus:ring-1 focus:ring-slate-400`}
                        >
                          {VALID_ELEMENTS.map((opt) => (
                            <option key={opt} value={opt}>
                              {opt}
                            </option>
                          ))}
                        </select>
                        <ChevronDown className="pointer-events-none absolute right-2 top-1.5 h-3 w-3 opacity-60 text-current" />
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span
                        className={`rounded-md px-2 py-0.5 font-mono text-[10px] font-bold border ${sourceStyle}`}
                      >
                        {sourceLabel}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-slate-600 tabular-nums whitespace-nowrap">
                      {formatCurrency(t.balance)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Footer Info */}
      <div className="flex items-center justify-between text-xs text-slate-500 px-1">
        <p>
          Showing {filteredTransactions.length} of {transactions.length} transactions
        </p>
        <p className="text-[11px] text-slate-400">
          Click any accounting category dropdown to re-assign an item
        </p>
      </div>
    </div>
  );
};
