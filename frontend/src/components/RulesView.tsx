import React, { useState } from 'react';
import { Plus, Search, SlidersHorizontal, Trash2 } from 'lucide-react';
import type { BackendRule, CategoryItem } from '../types';
import { normalizeElement } from '../types';
import { getCategoryBadge } from '../data/mockData';

interface RulesViewProps {
  rules: BackendRule[];
  onAddRule: (pattern: string, element: string, direction: string, priority: number) => Promise<void>;
  onDeleteRule: (ruleId: number) => Promise<void>;
  categories: CategoryItem[];
}

// Clean raw regex patterns like "\b(mtn|airtel|glo)\b" into human-friendly keyword lists
function formatKeywords(pattern: string): string[] {
  let cleaned = pattern.replace(/\\b/g, '').trim();
  if (cleaned.startsWith('(') && cleaned.endsWith(')')) {
    cleaned = cleaned.slice(1, -1);
  }
  const parts = cleaned.split('|').map((p) => p.trim()).filter(Boolean);
  return parts.length > 0 ? parts : [pattern];
}

export const RulesView: React.FC<RulesViewProps> = ({ rules, onAddRule, onDeleteRule, categories }) => {
  const [search, setSearch] = useState('');
  const [newPattern, setNewPattern] = useState('');
  const [newElement, setNewElement] = useState<string>('Expenses');
  const [newDirection, setNewDirection] = useState<'any' | 'debit' | 'credit'>('any');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const filteredRules = rules.filter(
    (r) =>
      r.pattern.toLowerCase().includes(search.toLowerCase()) ||
      r.element.toLowerCase().includes(search.toLowerCase())
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPattern.trim()) return;
    setIsSubmitting(true);
    try {
      const backendElem = newElement.toLowerCase().replace(' ', '_');
      await onAddRule(newPattern.trim().toUpperCase(), backendElem, newDirection, 50);
      setNewPattern('');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    setDeletingId(id);
    try {
      await onDeleteRule(id);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Create New Rule Form Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs">
        <h3 className="text-sm font-bold text-slate-900 mb-1">Create Automatic Categorization Rule</h3>
        <p className="text-xs text-slate-500 mb-4">
          Transactions matching this keyword will be categorized automatically without needing manual review.
        </p>

        <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-3 sm:grid-cols-12">
          <div className="sm:col-span-5">
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
              Narration Keyword or Merchant Name
            </label>
            <input
              type="text"
              placeholder="e.g. STARLINK, PAYSTACK, MTN, IKEJA ELECTRIC"
              value={newPattern}
              onChange={(e) => setNewPattern(e.target.value)}
              required
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 focus:border-emerald-500 focus:bg-white focus:outline-none"
            />
          </div>

          <div className="sm:col-span-3">
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
              Accounting Category
            </label>
            <select
              value={newElement}
              onChange={(e) => setNewElement(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700 focus:border-emerald-500 focus:bg-white focus:outline-none"
            >
              {categories.map((c) => (
                <option key={c.id} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div className="sm:col-span-2">
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
              Direction
            </label>
            <select
              value={newDirection}
              onChange={(e) => setNewDirection(e.target.value as 'any' | 'debit' | 'credit')}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700 focus:border-emerald-500 focus:bg-white focus:outline-none"
            >
              <option value="any">Any Flow</option>
              <option value="debit">Money Out</option>
              <option value="credit">Money In</option>
            </select>
          </div>

          <div className="sm:col-span-2 flex items-end">
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full inline-flex items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-2xs hover:bg-emerald-700 disabled:opacity-50 transition-colors"
            >
              <Plus className="h-4 w-4" />
              <span>{isSubmitting ? 'Saving...' : 'Add Rule'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Rules Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-2xs overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-100 p-4">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-emerald-600" />
            <h4 className="text-xs font-bold text-slate-900">Active Rules ({rules.length})</h4>
          </div>
          <div className="relative w-72">
            <Search className="absolute left-3 top-2 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search keyword or category..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 py-1 pl-8 pr-3 text-xs text-slate-900 focus:border-emerald-500 focus:bg-white focus:outline-none"
            />
          </div>
        </div>

        {/* Responsive Table with clear horizontal scroll */}
        <div className="overflow-x-auto w-full">
          <table className="w-full border-collapse text-left text-xs min-w-[650px]">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/80 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <th className="px-5 py-3.5 w-3/5">Matched Keywords / Merchants</th>
                <th className="px-5 py-3.5 w-1/5">Flow</th>
                <th className="px-5 py-3.5 w-1/5">Assigned Category</th>
                <th className="px-5 py-3.5 text-right w-16">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredRules.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-12 text-center text-slate-400">
                    No rules found matching "{search}"
                  </td>
                </tr>
              ) : (
                filteredRules.map((rule) => {
                  const elem = normalizeElement(rule.element);
                  const badge = getCategoryBadge(elem);
                  const keywords = formatKeywords(rule.pattern);

                  return (
                    <tr key={rule.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-5 py-3.5">
                        <div className="flex flex-wrap gap-1.5 max-w-xl">
                          {keywords.map((kw, i) => (
                            <span
                              key={i}
                              className="inline-block rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-800 border border-slate-200/80"
                            >
                              {kw}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-5 py-3.5 capitalize text-slate-600 font-medium">
                        {rule.direction === 'any' ? 'Any Flow' : `${rule.direction} only`}
                      </td>
                      <td className="px-5 py-3.5">
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold border ${badge.badge}`}
                        >
                          <span className={`h-1.5 w-1.5 rounded-full ${badge.dot}`} />
                          {elem}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <button
                          onClick={() => handleDelete(rule.id)}
                          disabled={deletingId === rule.id}
                          className="rounded p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600 transition-colors"
                          title="Delete rule"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
