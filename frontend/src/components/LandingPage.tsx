import React, { useState } from 'react';
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  FileSpreadsheet,
  Lock,
  Scale,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { ELEMENT_BADGE } from '../data/mockData';
import type { FinancialElement } from '../types';

const PREVIEW_ROWS: Array<{
  id: string;
  narration: string;
  amount: string;
  isCredit: boolean;
  element: FinancialElement;
  source: string;
}> = [
  {
    id: 'JRN-001',
    narration: 'PAYSTACK SETTLEMENT — CLIENT RETAINER #408',
    amount: '₦1,450,000.00',
    isCredit: true,
    element: 'Income',
    source: 'Rule',
  },
  {
    id: 'JRN-002',
    narration: 'SLOT SYSTEMS LTD — MACBOOK PRO WORKSTATION',
    amount: '₦1,250,000.00',
    isCredit: false,
    element: 'Assets',
    source: 'AI',
  },
  {
    id: 'JRN-003',
    narration: 'NIP TRF TO CHINEDU OKAFOR',
    amount: '₦320,000.00',
    isCredit: false,
    element: 'Needs Review',
    source: 'Review',
  },
  {
    id: 'JRN-004',
    narration: 'ACCESS WORKING CAPITAL LOAN REPAYMENT',
    amount: '₦275,000.00',
    isCredit: false,
    element: 'Liabilities',
    source: 'Rule',
  },
  {
    id: 'JRN-005',
    narration: 'DIRECTOR EQUITY CONTRIBUTION — OCT 2026',
    amount: '₦2,000,000.00',
    isCredit: true,
    element: 'Capital',
    source: 'Rule',
  },
];

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<string>('All');

  const visibleRows =
    filter === 'All'
      ? PREVIEW_ROWS
      : PREVIEW_ROWS.filter((r) => r.element === filter);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans flex flex-col selection:bg-emerald-100 selection:text-emerald-900">
      {/* Top Header */}
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur-sm">
        <div className="mx-auto flex h-18 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 font-bold text-sm text-white shadow-sm">
              LB
            </span>
            <span className="text-base font-bold tracking-tight text-slate-900">
              LedgerBridge
            </span>
          </div>

          <nav className="hidden items-center gap-6 text-xs font-semibold uppercase tracking-wider text-slate-500 md:flex">
            <a href="#workflow" className="hover:text-emerald-700 transition-colors">
              How It Works
            </a>
            <a href="#elements" className="hover:text-emerald-700 transition-colors">
              5 Accounting Elements
            </a>
            <a href="#security" className="hover:text-emerald-700 transition-colors">
              Data Privacy
            </a>
          </nav>

          <div className="flex items-center gap-3">
            <Link
              to="/login"
              className="text-xs font-semibold text-slate-600 hover:text-slate-900 px-3 py-1.5 transition-colors"
            >
              Sign In
            </Link>
            <Link
              to="/workspace"
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 transition-colors"
            >
              <span>Open Workspace</span>
              <ArrowUpRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="border-b border-slate-200 bg-white py-16 lg:py-24">
        <div className="mx-auto grid max-w-6xl gap-12 px-6 lg:grid-cols-12 lg:items-center">
          <div className="lg:col-span-6 space-y-6">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3.5 py-1 text-xs font-semibold text-emerald-800">
              <span className="h-2 w-2 rounded-full bg-emerald-600" />
              FINANCIAL LEDGER AUTOMATION
            </div>

            <h1 className="text-4xl font-extrabold tracking-tight text-slate-900 sm:text-5xl leading-[1.1]">
              Bank statements in.
              <br />
              <span className="text-emerald-600">Balanced ledgers</span> out.
            </h1>

            <p className="max-w-lg text-sm text-slate-600 leading-relaxed">
              Eliminate hours of manual reconciliation. LedgerBridge automatically ingests bank PDF
              and Excel statements, verifies row arithmetic, and organizes transactions into
              Assets, Liabilities, Income, Expenses, and Capital.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Link
                to="/workspace"
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-3 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 transition-colors"
              >
                <span>Launch Interactive Workspace</span>
                <ArrowRight className="h-4 w-4" />
              </Link>
              <a
                href="#workflow"
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-5 py-3 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
              >
                Learn More
              </a>
            </div>

            {/* Micro Metrics */}
            <div className="grid grid-cols-3 gap-4 border-t border-slate-100 pt-6">
              <div>
                <p className="font-mono text-xl font-bold text-slate-900">100%</p>
                <p className="text-xs text-slate-500">Local Privacy</p>
              </div>
              <div>
                <p className="font-mono text-xl font-bold text-slate-900">5</p>
                <p className="text-xs text-slate-500">Core Elements</p>
              </div>
              <div>
                <p className="font-mono text-xl font-bold text-emerald-600">Zoho / CSV</p>
                <p className="text-xs text-slate-500">Export Ready</p>
              </div>
            </div>
          </div>

          {/* Interactive Preview Table Card */}
          <div className="lg:col-span-6">
            <div className="rounded-2xl border border-slate-200 bg-white shadow-md overflow-hidden">
              <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-4 py-3">
                <span className="font-semibold text-xs text-slate-700">
                  Live Reconciliation Preview
                </span>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                  <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                  Arithmetic Balanced
                </span>
              </div>

              {/* Filter Tabs */}
              <div className="flex items-center gap-1 border-b border-slate-100 bg-white px-4 py-2 text-xs overflow-x-auto">
                {['All', 'Income', 'Assets', 'Liabilities', 'Capital', 'Needs Review'].map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                      filter === f
                        ? 'bg-slate-900 text-white'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>

              {/* Rows */}
              <div className="divide-y divide-slate-100">
                {visibleRows.map((row) => {
                  const badge = ELEMENT_BADGE[row.element];
                  return (
                    <div
                      key={row.id}
                      className="flex items-center justify-between p-3.5 hover:bg-slate-50/60 transition-colors"
                    >
                      <div className="space-y-0.5 max-w-[65%]">
                        <p className="font-medium text-xs text-slate-900 truncate">
                          {row.narration}
                        </p>
                        <span className="font-mono text-[10px] text-slate-400">
                          {row.source}
                        </span>
                      </div>

                      <div className="flex items-center gap-3">
                        <span
                          className={`font-mono text-xs font-bold tabular-nums ${
                            row.isCredit ? 'text-emerald-700' : 'text-slate-900'
                          }`}
                        >
                          {row.isCredit ? '+' : '-'}
                          {row.amount}
                        </span>
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold border ${badge.badge}`}
                        >
                          {row.element}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="border-t border-slate-100 bg-slate-50 p-3 text-center">
                <button
                  onClick={() => navigate('/workspace')}
                  className="text-xs font-semibold text-emerald-700 hover:text-emerald-800"
                >
                  Open full workspace to import statements →
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Pillars */}
      <section id="workflow" className="py-16">
        <div className="mx-auto max-w-6xl px-6">
          <div className="text-center max-w-xl mx-auto mb-12">
            <h2 className="text-2xl font-bold text-slate-900">
              Built for Accountants, Bookkeepers, and Finance Teams
            </h2>
            <p className="mt-2 text-xs text-slate-500 leading-relaxed">
              Fast, accurate, and structured around your double-entry accounting workflows.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-2xs">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                <FileSpreadsheet className="h-5 w-5" />
              </div>
              <h3 className="mt-4 text-sm font-bold text-slate-900">Bank Statement Math Integrity</h3>
              <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                Verifies opening balances, deposits, withdrawals, and ending balance arithmetic
                automatically on upload. Discrepancies are flagged immediately.
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-2xs">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                <Scale className="h-5 w-5" />
              </div>
              <h3 className="mt-4 text-sm font-bold text-slate-900">Review Queue & Smart Memory</h3>
              <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                Ambiguous transfers are isolated in a clean triage queue. Confirming a mapping
                remembers the vendor pattern so you never have to reclassify it again.
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-2xs">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                <Lock className="h-5 w-5" />
              </div>
              <h3 className="mt-4 text-sm font-bold text-slate-900">100% Offline Data Privacy</h3>
              <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                Your bank statements and customer financials never leave your machine. Processing
                and database storage occur entirely on your local machine.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-200 bg-white py-6 text-center text-xs text-slate-400">
        <p>LedgerBridge · Financial Bank Statement Reconciler</p>
      </footer>
    </div>
  );
};
