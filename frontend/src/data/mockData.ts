import type { FinancialElement } from '../types';

export const ELEMENT_BADGE: Record<
  FinancialElement,
  { dot: string; badge: string; border: string; glow: string }
> = {
  Assets: {
    dot: 'bg-sky-500',
    badge: 'bg-sky-50 text-sky-700 border-sky-200',
    border: 'border-sky-300',
    glow: 'shadow-sm',
  },
  Liabilities: {
    dot: 'bg-purple-500',
    badge: 'bg-purple-50 text-purple-700 border-purple-200',
    border: 'border-purple-300',
    glow: 'shadow-sm',
  },
  Income: {
    dot: 'bg-emerald-500',
    badge: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    border: 'border-emerald-300',
    glow: 'shadow-sm',
  },
  Expenses: {
    dot: 'bg-rose-500',
    badge: 'bg-rose-50 text-rose-700 border-rose-200',
    border: 'border-rose-300',
    glow: 'shadow-sm',
  },
  Capital: {
    dot: 'bg-teal-500',
    badge: 'bg-teal-50 text-teal-700 border-teal-200',
    border: 'border-teal-300',
    glow: 'shadow-sm',
  },
  'Needs Review': {
    dot: 'bg-amber-500 animate-pulse',
    badge: 'bg-amber-50 text-amber-800 border-amber-200',
    border: 'border-amber-300',
    glow: 'shadow-sm',
  },
};
