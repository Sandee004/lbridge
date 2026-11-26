import React, { useState } from 'react';
import {
  CheckCircle2,
  KeyRound,
  Layers,
  Lock,
  Plus,
  Save,
  Trash2,
  User,
} from 'lucide-react';
import { PasswordInput } from './PasswordInput';
import type { CategoryItem } from '../types';
import { getCategoryBadge } from '../data/mockData';

interface SettingsViewProps {
  userEmail: string;
  onShowToast: (msg: string, type?: 'success' | 'error') => void;
  categories: CategoryItem[];
  onAddCategory: (
    name: string,
    direction: string,
    color: string,
    description?: string
  ) => Promise<void>;
  onDeleteCategory: (id: number) => Promise<void>;
}

const AVAILABLE_COLORS = [
  { label: 'Sky Blue', value: 'sky' },
  { label: 'Purple', value: 'purple' },
  { label: 'Emerald Green', value: 'emerald' },
  { label: 'Rose Red', value: 'rose' },
  { label: 'Teal', value: 'teal' },
  { label: 'Amber Yellow', value: 'amber' },
  { label: 'Indigo', value: 'indigo' },
  { label: 'Orange', value: 'orange' },
  { label: 'Slate Gray', value: 'slate' },
];

export const SettingsView: React.FC<SettingsViewProps> = ({
  userEmail,
  onShowToast,
  categories,
  onAddCategory,
  onDeleteCategory,
}) => {
  const [displayName, setDisplayName] = useState('Finance Operations');
  const [companyName, setCompanyName] = useState('Access Capital Ltd');
  const [baseCurrency, setBaseCurrency] = useState('NGN');
  const [capitalizationThreshold, setCapitalizationThreshold] = useState('500000');

  // Password fields
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordSaved, setPasswordSaved] = useState(false);

  // New Category fields
  const [catName, setCatName] = useState('');
  const [catDirection, setCatDirection] = useState<'any' | 'debit' | 'credit'>('debit');
  const [catColor, setCatColor] = useState('slate');
  const [catDescription, setCatDescription] = useState('');
  const [isAddingCategory, setIsAddingCategory] = useState(false);
  const [deletingCatId, setDeletingCatId] = useState<number | null>(null);

  const handleSaveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    onShowToast('Account & accounting preferences updated successfully.');
  };

  const handleUpdatePassword = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPassword || newPassword !== confirmPassword) {
      alert('New password and confirm password do not match.');
      return;
    }
    setPasswordSaved(true);
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
    onShowToast('Password changed successfully.');
    setTimeout(() => setPasswordSaved(false), 3000);
  };

  const handleCreateCategorySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!catName.trim()) return;

    setIsAddingCategory(true);
    try {
      await onAddCategory(catName.trim(), catDirection, catColor, catDescription.trim() || undefined);
      setCatName('');
      setCatDescription('');
      setCatDirection('debit');
      setCatColor('slate');
    } catch {
      // Error handled by parent toast
    } finally {
      setIsAddingCategory(false);
    }
  };

  const handleDeleteCategoryClick = async (id: number) => {
    setDeletingCatId(id);
    try {
      await onDeleteCategory(id);
    } finally {
      setDeletingCatId(null);
    }
  };

  return (
    <div className="max-w-4xl space-y-6">
      {/* Profile & Organization Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-2xs">
        <div className="flex items-center gap-3 border-b border-slate-100 pb-4 mb-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
            <User className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">Profile & Organization</h3>
            <p className="text-xs text-slate-500">
              Manage your company information and default accounting currency
            </p>
          </div>
        </div>

        <form onSubmit={handleSaveProfile} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Display Name
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 focus:border-emerald-500 focus:bg-white focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Email Address
              </label>
              <input
                type="email"
                value={userEmail}
                disabled
                className="w-full rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-xs text-slate-500 cursor-not-allowed"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Company / Organization Name
              </label>
              <input
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 focus:border-emerald-500 focus:bg-white focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Base Statement Currency
              </label>
              <select
                value={baseCurrency}
                onChange={(e) => setBaseCurrency(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700 focus:border-emerald-500 focus:bg-white focus:outline-none"
              >
                <option value="NGN">NGN (₦) — Nigerian Naira</option>
                <option value="USD">USD ($) — United States Dollar</option>
                <option value="GBP">GBP (£) — British Pound</option>
                <option value="EUR">EUR (€) — Euro</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Fixed Asset Capitalization Threshold (₦)
            </label>
            <p className="text-[11px] text-slate-400 mb-1.5">
              Purchases above this amount are evaluated as Assets (Capex) rather than immediate Expenses.
            </p>
            <input
              type="number"
              value={capitalizationThreshold}
              onChange={(e) => setCapitalizationThreshold(e.target.value)}
              className="max-w-xs rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 focus:border-emerald-500 focus:bg-white focus:outline-none font-mono"
            />
          </div>

          <div className="pt-2">
            <button
              type="submit"
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-2xs hover:bg-emerald-700 transition-colors"
            >
              <Save className="h-4 w-4" />
              <span>Save Preferences</span>
            </button>
          </div>
        </form>
      </div>

      {/* Accounting Categories & Chart of Accounts Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-2xs">
        <div className="flex items-center gap-3 border-b border-slate-100 pb-4 mb-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-700">
            <Layers className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Accounting Categories & Chart of Accounts
            </h3>
            <p className="text-xs text-slate-500">
              Configure accounting categories matching Zoho Books, QuickBooks, or custom internal ledgers.
            </p>
          </div>
        </div>

        {/* Create Custom Category Form */}
        <div className="mb-6 rounded-lg border border-slate-100 bg-slate-50 p-4">
          <h4 className="text-xs font-bold text-slate-900 mb-1 flex items-center gap-1.5">
            <Plus className="h-4 w-4 text-emerald-600" />
            <span>Add Custom Category</span>
          </h4>
          <p className="text-[11px] text-slate-500 mb-3">
            Create additional transaction categories beyond the standard 5 elements (e.g. Cost of Goods Sold, Marketing, Internal Transfer).
          </p>

          <form onSubmit={handleCreateCategorySubmit} className="grid grid-cols-1 gap-3 sm:grid-cols-12">
            <div className="sm:col-span-4">
              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
                Category Name
              </label>
              <input
                type="text"
                placeholder="e.g. Cost of Goods Sold, Marketing, Transfer"
                value={catName}
                onChange={(e) => setCatName(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-900 focus:border-emerald-500 focus:outline-none"
              />
            </div>

            <div className="sm:col-span-3">
              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
                Allowed Flow Direction
              </label>
              <select
                value={catDirection}
                onChange={(e) => setCatDirection(e.target.value as 'any' | 'debit' | 'credit')}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 focus:border-emerald-500 focus:outline-none"
              >
                <option value="debit">Money Out (Debit)</option>
                <option value="credit">Money In (Credit)</option>
                <option value="any">Any Flow (In or Out)</option>
              </select>
            </div>

            <div className="sm:col-span-2">
              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
                Badge Color
              </label>
              <select
                value={catColor}
                onChange={(e) => setCatColor(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 focus:border-emerald-500 focus:outline-none"
              >
                {AVAILABLE_COLORS.map((col) => (
                  <option key={col.value} value={col.value}>
                    {col.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="sm:col-span-3">
              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
                Description (Optional)
              </label>
              <input
                type="text"
                placeholder="Short accounting memo"
                value={catDescription}
                onChange={(e) => setCatDescription(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-900 focus:border-emerald-500 focus:outline-none"
              />
            </div>

            <div className="sm:col-span-12 flex justify-end">
              <button
                type="submit"
                disabled={isAddingCategory || !catName.trim()}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-2xs hover:bg-emerald-700 disabled:opacity-50 transition-colors"
              >
                <Plus className="h-4 w-4" />
                <span>{isAddingCategory ? 'Adding...' : 'Save Category'}</span>
              </button>
            </div>
          </form>
        </div>

        {/* Existing Categories Table */}
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                <th className="py-2.5 px-3">Category</th>
                <th className="py-2.5 px-3">Direction</th>
                <th className="py-2.5 px-3">Description</th>
                <th className="py-2.5 px-3">Type</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {categories.map((cat) => {
                const badge = getCategoryBadge(cat.name, cat.color);
                return (
                  <tr key={cat.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <span className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-0.5 font-semibold text-xs ${badge.badge}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${badge.dot}`} />
                        <span>{cat.name}</span>
                      </span>
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap text-slate-600 capitalize">
                      {cat.direction === 'debit'
                        ? 'Money Out (Debit)'
                        : cat.direction === 'credit'
                        ? 'Money In (Credit)'
                        : 'Any Direction'}
                    </td>
                    <td className="py-2.5 px-3 text-slate-500 max-w-xs truncate">
                      {cat.description || '—'}
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          cat.is_system
                            ? 'bg-slate-100 text-slate-600'
                            : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        }`}
                      >
                        {cat.is_system ? 'Core Default' : 'Custom Category'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right whitespace-nowrap">
                      {!cat.is_system && (
                        <button
                          onClick={() => handleDeleteCategoryClick(cat.id)}
                          disabled={deletingCatId === cat.id}
                          className="text-rose-600 hover:text-rose-800 disabled:opacity-40 p-1 rounded transition-colors"
                          title="Delete custom category"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Security & Password Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-2xs">
        <div className="flex items-center gap-3 border-b border-slate-100 pb-4 mb-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
            <KeyRound className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">Security & Password</h3>
            <p className="text-xs text-slate-500">
              Update your account credentials used to unlock your local workspace
            </p>
          </div>
        </div>

        {passwordSaved && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2 text-xs text-emerald-800">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
            <span>Password updated successfully.</span>
          </div>
        )}

        <form onSubmit={handleUpdatePassword} className="space-y-4 max-w-lg">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Current Password
            </label>
            <PasswordInput
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="••••••••••••"
              required
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                New Password
              </label>
              <PasswordInput
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="At least 8 characters"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Confirm New Password
              </label>
              <PasswordInput
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter password"
                required
              />
            </div>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition-colors"
            >
              <Lock className="h-4 w-4 text-slate-400" />
              <span>Update Password</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
