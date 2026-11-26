export const COLOR_STYLES: Record<
  string,
  { dot: string; badge: string; border: string; glow: string }
> = {
  sky: {
    dot: 'bg-sky-500',
    badge: 'bg-sky-50 text-sky-700 border-sky-200',
    border: 'border-sky-300',
    glow: 'shadow-2xs',
  },
  purple: {
    dot: 'bg-purple-500',
    badge: 'bg-purple-50 text-purple-700 border-purple-200',
    border: 'border-purple-300',
    glow: 'shadow-2xs',
  },
  emerald: {
    dot: 'bg-emerald-500',
    badge: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    border: 'border-emerald-300',
    glow: 'shadow-2xs',
  },
  rose: {
    dot: 'bg-rose-500',
    badge: 'bg-rose-50 text-rose-700 border-rose-200',
    border: 'border-rose-300',
    glow: 'shadow-2xs',
  },
  teal: {
    dot: 'bg-teal-500',
    badge: 'bg-teal-50 text-teal-700 border-teal-200',
    border: 'border-teal-300',
    glow: 'shadow-2xs',
  },
  amber: {
    dot: 'bg-amber-500',
    badge: 'bg-amber-50 text-amber-700 border-amber-200',
    border: 'border-amber-300',
    glow: 'shadow-2xs',
  },
  indigo: {
    dot: 'bg-indigo-500',
    badge: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    border: 'border-indigo-300',
    glow: 'shadow-2xs',
  },
  orange: {
    dot: 'bg-orange-500',
    badge: 'bg-orange-50 text-orange-700 border-orange-200',
    border: 'border-orange-300',
    glow: 'shadow-2xs',
  },
  slate: {
    dot: 'bg-slate-500',
    badge: 'bg-slate-100 text-slate-700 border-slate-300',
    border: 'border-slate-400',
    glow: 'shadow-2xs',
  },
};

export const ELEMENT_BADGE: Record<
  string,
  { dot: string; badge: string; border: string; glow: string }
> = {
  Assets: COLOR_STYLES.sky,
  Liabilities: COLOR_STYLES.purple,
  Income: COLOR_STYLES.emerald,
  Expenses: COLOR_STYLES.rose,
  Capital: COLOR_STYLES.teal,
  'Cost of Goods Sold': COLOR_STYLES.amber,
  'Internal Transfer': COLOR_STYLES.indigo,
  'Taxes & VAT': COLOR_STYLES.orange,
  'Needs Review': {
    dot: 'bg-amber-500 animate-pulse',
    badge: 'bg-amber-50 text-amber-800 border-amber-200',
    border: 'border-amber-300',
    glow: 'shadow-2xs',
  },
};

export function getCategoryBadge(
  element: string,
  color?: string
): { dot: string; badge: string; border: string; glow: string } {
  if (element === 'Needs Review') return ELEMENT_BADGE['Needs Review'];
  if (ELEMENT_BADGE[element]) return ELEMENT_BADGE[element];
  if (color && COLOR_STYLES[color]) return COLOR_STYLES[color];
  return COLOR_STYLES.slate;
}
