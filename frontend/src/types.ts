export type FinancialElement = string;

export interface CategoryItem {
  id: number;
  name: string;
  slug: string;
  direction: 'any' | 'debit' | 'credit';
  color: string;
  description?: string | null;
  is_system: boolean;
  created_at?: string | null;
}

export type ClassificationTier = 'rule' | 'llm' | 'user' | 'validator' | 'ingestion';

export interface BackendTransaction {
  id: string;
  statement_id: string;
  fingerprint?: string | null;
  date: string;
  value_date?: string | null;
  amount: number;
  direction: 'credit' | 'debit';
  description_raw: string;
  description_norm: string;
  balance?: number | null;
  element?: string | null;
  tier?: ClassificationTier | string | null;
  rule_id?: number | null;
  confidence?: number | null;
  reason?: string | null;
  status?: string | null;
}

export interface BackendStatement {
  id: string;
  filename: string;
  bank_name: string;
  currency: string;
  period_start?: string | null;
  period_end?: string | null;
  opening_balance?: number | null;
  closing_balance?: number | null;
  total_credits?: number | null;
  total_debits?: number | null;
  math_ok: boolean;
  math_error_detail?: string | null;
  transaction_count: number;
  transactions: BackendTransaction[];
}

export interface BackendRule {
  id: number;
  pattern: string;
  match_type: string;
  direction: string;
  element: string;
  priority: number;
  source: string;
  hit_count: number;
  active: boolean;
  created_at?: string | null;
}

export interface UploadSummary {
  statement_id: string;
  filename: string;
  bank_name: string;
  currency: string;
  math_ok: boolean;
  math_error_detail?: string | null;
  opening_balance?: number | null;
  closing_balance?: number | null;
  total_credits?: number | null;
  total_debits?: number | null;
  total_rows_parsed: number;
  new_rows_stored: number;
  duplicates_skipped: number;
  rules_count: number;
  llm_count: number;
  needs_review_count: number;
  message: string;
}

export type AppView = 'landing' | 'auth' | 'workspace';
export type WorkspacePage = 'overview' | 'review' | 'ledger' | 'rules' | 'settings';

// Helper to normalize element to UI display name
export function normalizeElement(raw?: string | null): string {
  if (!raw) return 'Needs Review';
  const lower = raw.toLowerCase().trim();
  if (lower === 'needs_review' || lower === 'needs review') return 'Needs Review';
  if (lower === 'asset' || lower === 'assets') return 'Assets';
  if (lower === 'liability' || lower === 'liabilities') return 'Liabilities';
  if (lower === 'income') return 'Income';
  if (lower === 'expense' || lower === 'expenses') return 'Expenses';
  if (lower === 'capital' || lower === 'equity') return 'Capital';
  if (lower === 'cogs' || lower === 'cost_of_goods_sold' || lower === 'cost of goods sold') return 'Cost of Goods Sold';
  if (lower === 'transfer' || lower === 'internal_transfer' || lower === 'internal transfer') return 'Internal Transfer';
  if (lower === 'taxes' || lower === 'taxes_and_vat' || lower === 'taxes & vat' || lower === 'tax') return 'Taxes & VAT';
  
  // Custom categories: convert snake_case to Title Case
  return raw
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// Helper to convert UI display name to backend element value
export function toBackendElement(elem: string): string {
  const lower = elem.toLowerCase().trim();
  if (lower === 'needs review' || lower === 'needs_review') return 'needs_review';
  if (lower === 'assets' || lower === 'asset') return 'asset';
  if (lower === 'liabilities' || lower === 'liability') return 'liability';
  if (lower === 'expenses' || lower === 'expense') return 'expense';
  if (lower === 'cost of goods sold' || lower === 'cogs') return 'cogs';
  if (lower === 'internal transfer' || lower === 'transfer') return 'transfer';
  if (lower === 'taxes & vat' || lower === 'taxes and vat' || lower === 'taxes') return 'taxes';
  return lower.replace(/\s+/g, '_');
}
