import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import type {
  BackendRule,
  BackendStatement,
  BackendTransaction,
  CategoryItem,
  UploadSummary,
  WorkspacePage,
} from '../types';
import { normalizeElement } from '../types';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { OverviewView } from './OverviewView';
import { ReviewQueueView } from './ReviewQueueView';
import { LedgerView } from './LedgerView';
import { RulesView } from './RulesView';
import { SettingsView } from './SettingsView';

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : window.location.port === '5173'
    ? ''
    : 'http://127.0.0.1:8000';

const VALID_PAGES: WorkspacePage[] = ['overview', 'review', 'ledger', 'rules', 'settings'];

const formatCurrency = (val?: number | null) => {
  if (val === null || val === undefined) return '₦0.00';
  return `₦${val.toLocaleString('en-NG', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};

// Clean any accidental model names from human display
function sanitizeReason(reason?: string | null): string | undefined {
  if (!reason) return undefined;
  const cleaned = reason
    .replace(/Qwen \([^)]+\):\s*/gi, '')
    .replace(/qwen2\.5[^\s:]*:\s*/gi, '')
    .replace(/qwen:\s*/gi, '')
    .trim();
  return cleaned || undefined;
}

export const Workspace: React.FC = () => {
  const { page } = useParams<{ page?: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Validate current page from URL
  const currentPage: WorkspacePage =
    page && VALID_PAGES.includes(page as WorkspacePage)
      ? (page as WorkspacePage)
      : 'overview';

  const [ledgerElementFilter, setLedgerElementFilter] = useState<string>('All');

  // Active Statement from URL search param or localStorage
  const initialStatementId =
    searchParams.get('statement') || localStorage.getItem('lb_active_statement') || 'all';
  const [selectedStatementId, setSelectedStatementId] = useState<string>(initialStatementId);

  // User Profile
  const [userEmail, setUserEmail] = useState<string>(() => {
    const raw = localStorage.getItem('lb_user');
    if (raw) {
      try {
        return JSON.parse(raw).email || 'finance@company.com';
      } catch {
        return 'finance@company.com';
      }
    }
    return 'finance@company.com';
  });

  // Backend Data State
  const [statements, setStatements] = useState<BackendStatement[]>([]);
  const [rules, setRules] = useState<BackendRule[]>([]);
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<string>('');
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  // ------------------------------
  // Component-Local API Calls (Using HttpOnly Cookies)
  // ------------------------------

  const fetchStatementsAPI = async (): Promise<BackendStatement[]> => {
    const res = await fetch(`${BASE_URL}/statements`, { credentials: 'include' });
    if (!res.ok) throw new Error('Failed to load statements');
    const data: BackendStatement[] = await res.json();
    return data.map((s) => ({
      ...s,
      transactions: (s.transactions || []).map((t) => ({
        ...t,
        reason: sanitizeReason(t.reason),
      })),
    }));
  };

  const fetchRulesAPI = async (): Promise<BackendRule[]> => {
    const res = await fetch(`${BASE_URL}/statements/rules`, { credentials: 'include' });
    if (!res.ok) return [];
    return res.json();
  };

  const uploadStatementAPI = async (file: File): Promise<UploadSummary> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${BASE_URL}/statements/upload`, {
      method: 'POST',
      credentials: 'include',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  };

  const loadSampleAPI = async (sampleName: 'access-bank-pdf' | 'demo-excel'): Promise<UploadSummary> => {
    const res = await fetch(`${BASE_URL}/statements/sample/${sampleName}`, {
      method: 'POST',
      credentials: 'include',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Sample load failed' }));
      throw new Error(err.detail || 'Sample load failed');
    }
    return res.json();
  };

  const updateTransactionAPI = async (
    txnId: string,
    element: string,
    createRule: boolean = false,
    rulePattern?: string,
    ruleDirection: string = 'any'
  ): Promise<BackendTransaction> => {
    const res = await fetch(`${BASE_URL}/statements/transactions/${txnId}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        element,
        create_rule: createRule,
        rule_pattern: rulePattern,
        rule_direction: ruleDirection,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Update failed' }));
      throw new Error(err.detail || 'Failed to update transaction');
    }
    const updated: BackendTransaction = await res.json();
    return { ...updated, reason: sanitizeReason(updated.reason) };
  };

  const createRuleAPI = async (
    pattern: string,
    element: string,
    direction: string = 'any',
    priority: number = 50
  ): Promise<BackendRule> => {
    const res = await fetch(`${BASE_URL}/statements/rules`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pattern, element, direction, priority }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Rule creation failed' }));
      throw new Error(err.detail || 'Failed to create rule');
    }
    return res.json();
  };

  const deleteRuleAPI = async (ruleId: number): Promise<void> => {
    const res = await fetch(`${BASE_URL}/statements/rules/${ruleId}`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (!res.ok) throw new Error('Failed to delete rule');
  };

  const fetchCategoriesAPI = async (): Promise<CategoryItem[]> => {
    const res = await fetch(`${BASE_URL}/statements/categories`, { credentials: 'include' });
    if (!res.ok) return [];
    return res.json();
  };

  const createCategoryAPI = async (
    name: string,
    direction: string = 'debit',
    color: string = 'slate',
    description?: string
  ): Promise<CategoryItem> => {
    const res = await fetch(`${BASE_URL}/statements/categories`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, direction, color, description }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to create category' }));
      throw new Error(err.detail || 'Failed to create category');
    }
    return res.json();
  };

  const deleteCategoryAPI = async (categoryId: number): Promise<void> => {
    const res = await fetch(`${BASE_URL}/statements/categories/${categoryId}`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to delete category' }));
      throw new Error(err.detail || 'Failed to delete category');
    }
  };

  const handleLogout = async () => {
    try {
      await fetch(`${BASE_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch {
      // Ignore network errors on logout
    }
    localStorage.removeItem('lb_user');
    localStorage.removeItem('lb_active_statement');
    navigate('/login');
  };

  // ------------------------------
  // Initial Data Fetch
  // ------------------------------

  const refreshData = async () => {
    try {
      const [fetchedStatements, fetchedRules, fetchedCategories] = await Promise.all([
        fetchStatementsAPI(),
        fetchRulesAPI(),
        fetchCategoriesAPI(),
      ]);
      setStatements(fetchedStatements);
      setRules(fetchedRules);
      setCategories(fetchedCategories);
    } catch (err: unknown) {
      if (err instanceof Error && err.message !== 'UNAUTHORIZED') {
        showToast(err.message, 'error');
      }
    }
  };

  useEffect(() => {
    let active = true;

    async function initialize() {
      try {
        const [fetchedStatements, fetchedRules, fetchedCategories] = await Promise.all([
          fetchStatementsAPI(),
          fetchRulesAPI(),
          fetchCategoriesAPI(),
        ]);
        if (active) {
          setStatements(fetchedStatements);
          setRules(fetchedRules);
          setCategories(fetchedCategories);

          // Restore or select first statement
          if (fetchedStatements.length > 0) {
            const exists = fetchedStatements.some((s) => s.id === initialStatementId);
            if (!exists && initialStatementId !== 'all') {
              setSelectedStatementId(fetchedStatements[0].id);
            }
          }

          // Fetch current user profile if available
          fetch(`${BASE_URL}/auth/me`, { credentials: 'include' })
            .then((r) => (r.ok ? r.json() : null))
            .then((u) => {
              if (u?.email && active) {
                setUserEmail(u.email);
                localStorage.setItem('lb_user', JSON.stringify(u));
              }
            })
            .catch(() => {});
        }
      } catch (err: unknown) {
        if (active && err instanceof Error && err.message !== 'UNAUTHORIZED') {
          showToast(err.message, 'error');
        }
      }
    }

    initialize();

    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigate]);

  // Handle URL Page Switching
  const handlePageChange = (newPage: WorkspacePage) => {
    const currentStatement = searchParams.get('statement');
    const query = currentStatement ? `?statement=${currentStatement}` : '';
    navigate(`/workspace/${newPage}${query}`);
  };

  // Handle Statement Switching with persistence
  const handleSelectStatement = (id: string) => {
    setSelectedStatementId(id);
    localStorage.setItem('lb_active_statement', id);
    setSearchParams((prev) => {
      const updated = new URLSearchParams(prev);
      if (id === 'all') {
        updated.delete('statement');
      } else {
        updated.set('statement', id);
      }
      return updated;
    });
  };

  // Compute Active Statement & Transactions
  const activeStatement = useMemo(() => {
    if (selectedStatementId === 'all') return null;
    return statements.find((s) => s.id === selectedStatementId) || null;
  }, [statements, selectedStatementId]);

  const allTransactions = useMemo(() => {
    if (activeStatement) {
      return activeStatement.transactions || [];
    }
    return statements.flatMap((s) => s.transactions || []);
  }, [statements, activeStatement]);

  // Unreconciled Queue
  const pendingTransactions = useMemo(() => {
    return allTransactions.filter((t) => normalizeElement(t.element) === 'Needs Review');
  }, [allTransactions]);

  // Totals
  const elementTotals = useMemo(() => {
    const totals: Record<string, number> = {};
    let totalCredits = 0;
    let totalDebits = 0;

    categories.forEach((c) => {
      totals[c.name] = 0;
    });
    ['Assets', 'Liabilities', 'Income', 'Expenses', 'Capital', 'Cost of Goods Sold', 'Internal Transfer', 'Taxes & VAT'].forEach((k) => {
      if (totals[k] === undefined) totals[k] = 0;
    });

    allTransactions.forEach((t) => {
      const elem = normalizeElement(t.element);
      if (elem !== 'Needs Review') {
        totals[elem] = (totals[elem] || 0) + t.amount;
      }
      if (t.direction === 'credit') {
        totalCredits += t.amount;
      } else {
        totalDebits += t.amount;
      }
    });

    return { ...totals, totalCredits, totalDebits, netFlow: totalCredits - totalDebits };
  }, [allTransactions, categories]);

  // Handlers
  const handleResolve = async (
    tx: BackendTransaction,
    chosenElement: string,
    saveRule: boolean
  ) => {
    const cleanPattern = tx.description_norm || tx.description_raw.split(/[-–—/]/)[0].trim();
    const patternToSave = cleanPattern.slice(0, 32).toUpperCase();

    try {
      const updated = await updateTransactionAPI(
        tx.id,
        chosenElement,
        saveRule,
        patternToSave,
        tx.direction
      );

      setStatements((prev) =>
        prev.map((s) => ({
          ...s,
          transactions: s.transactions.map((t) => (t.id === tx.id ? { ...t, ...updated } : t)),
        }))
      );

      if (saveRule) {
        showToast(`Categorized as ${chosenElement} and saved rule for "${patternToSave}"`);
        fetchRulesAPI().then(setRules).catch(() => {});
      } else {
        showToast(`Categorized as ${chosenElement}`);
      }
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : 'Failed to update transaction', 'error');
    }
  };

  const handleReclassify = async (txnId: string, newElement: string) => {
    try {
      const updated = await updateTransactionAPI(txnId, newElement, false);
      setStatements((prev) =>
        prev.map((s) => ({
          ...s,
          transactions: s.transactions.map((t) => (t.id === txnId ? { ...t, ...updated } : t)),
        }))
      );
      showToast(`Assigned to ${newElement}`);
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : 'Update failed', 'error');
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadProgress(`Importing and analyzing ${file.name}...`);

    try {
      const summary = await uploadStatementAPI(file);
      showToast(`Imported ${summary.total_rows_parsed} transactions from ${file.name}`);
      await refreshData();
      handleSelectStatement(summary.statement_id);
      if (summary.needs_review_count > 0) {
        handlePageChange('review');
      } else {
        handlePageChange('ledger');
      }
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : 'Import failed', 'error');
    } finally {
      setIsUploading(false);
      setUploadProgress('');
      e.target.value = '';
    }
  };

  const handleLoadSample = async (sampleType: 'access-bank-pdf' | 'demo-excel') => {
    setIsUploading(true);
    setUploadProgress(
      sampleType === 'access-bank-pdf'
        ? 'Importing Access Bank Statement (PDF)...'
        : 'Importing Corporate Statement (.XLSX)...'
    );
    try {
      const summary = await loadSampleAPI(sampleType);
      showToast(`Loaded sample statement: ${summary.bank_name}`);
      await refreshData();
      handleSelectStatement(summary.statement_id);
      handlePageChange(summary.needs_review_count > 0 ? 'review' : 'overview');
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : 'Sample import failed', 'error');
    } finally {
      setIsUploading(false);
      setUploadProgress('');
    }
  };

  const handleAddRule = async (
    pattern: string,
    element: string,
    direction: string,
    priority: number
  ) => {
    const newRule = await createRuleAPI(pattern, element, direction, priority);
    setRules((prev) => [newRule, ...prev]);
    showToast(`Saved categorization rule for "${pattern}"`);
  };

  const handleDeleteRule = async (ruleId: number) => {
    await deleteRuleAPI(ruleId);
    setRules((prev) => prev.filter((r) => r.id !== ruleId));
    showToast('Rule removed');
  };

  const handleAddCategory = async (
    name: string,
    direction: string,
    color: string,
    description?: string
  ) => {
    try {
      const newCat = await createCategoryAPI(name, direction, color, description);
      setCategories((prev) => [...prev, newCat]);
      showToast(`Created category "${newCat.name}"`);
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : 'Failed to create category', 'error');
      throw err;
    }
  };

  const handleDeleteCategory = async (categoryId: number) => {
    try {
      await deleteCategoryAPI(categoryId);
      setCategories((prev) => prev.filter((c) => c.id !== categoryId));
      showToast('Category deleted');
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : 'Failed to delete category', 'error');
      throw err;
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex font-sans text-slate-900 selection:bg-emerald-100 selection:text-emerald-900">
      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-xl border px-4 py-3 text-xs font-semibold shadow-lg transition-all animate-bounce ${
            toast.type === 'error'
              ? 'border-rose-200 bg-rose-50 text-rose-800'
              : 'border-emerald-200 bg-white text-emerald-800 shadow-emerald-50'
          }`}
        >
          {toast.type === 'error' ? (
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
          ) : (
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
          )}
          <span>{toast.message}</span>
        </div>
      )}

      {/* LEFT SIDEBAR NAVIGATION */}
      <Sidebar
        currentPage={currentPage}
        onPageChange={handlePageChange}
        pendingCount={pendingTransactions.length}
        statements={statements}
        selectedStatementId={selectedStatementId}
        onSelectStatement={handleSelectStatement}
        onLoadSample={handleLoadSample}
        onLogout={handleLogout}
        userEmail={userEmail}
        isUploading={isUploading}
      />

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-y-auto">
        {/* MINIMAL TOP HEADER */}
        <Header
          currentPage={currentPage}
          onPageChange={handlePageChange}
          onFileUpload={handleFileUpload}
          isUploading={isUploading}
          transactions={allTransactions}
          activeStatementName={activeStatement?.bank_name}
          activeStatementId={activeStatement?.id}
        />

        {/* UPLOADING FEEDBACK STRIP */}
        {isUploading && (
          <div className="bg-emerald-50 border-b border-emerald-200 px-8 py-3 text-xs text-emerald-800 flex items-center gap-2.5">
            <RefreshCw className="h-4 w-4 animate-spin text-emerald-600" />
            <span className="font-medium">{uploadProgress}</span>
          </div>
        )}

        {/* PAGE CONTENT */}
        <main className="p-8 max-w-7xl w-full mx-auto">
          {currentPage === 'overview' && (
            <OverviewView
              activeStatement={activeStatement}
              elementTotals={elementTotals}
              pendingCount={pendingTransactions.length}
              onNavigate={handlePageChange}
              onFilterElement={(elem) => {
                setLedgerElementFilter(elem);
                handlePageChange('ledger');
              }}
              formatCurrency={formatCurrency}
              categories={categories}
            />
          )}

          {currentPage === 'review' && (
            <ReviewQueueView
              pendingTransactions={pendingTransactions}
              onResolve={handleResolve}
              onNavigate={handlePageChange}
              formatCurrency={formatCurrency}
              categories={categories}
            />
          )}

          {currentPage === 'ledger' && (
            <LedgerView
              transactions={allTransactions}
              onReclassify={handleReclassify}
              formatCurrency={formatCurrency}
              initialElementFilter={ledgerElementFilter}
              categories={categories}
            />
          )}

          {currentPage === 'rules' && (
            <RulesView
              rules={rules}
              onAddRule={handleAddRule}
              onDeleteRule={handleDeleteRule}
              categories={categories}
            />
          )}

          {currentPage === 'settings' && (
            <SettingsView
              userEmail={userEmail}
              onShowToast={showToast}
              categories={categories}
              onAddCategory={handleAddCategory}
              onDeleteCategory={handleDeleteCategory}
            />
          )}
        </main>
      </div>
    </div>
  );
};
