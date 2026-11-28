# LedgerBridge

> **The Privacy-First, Local AI Pre-Accounting Engine for Bank Statements**  
> Parse messy Nigerian bank statement PDFs and Excel sheets, verify the arithmetic, and auto-classify transactions across your Chart of Accounts—exporting clean, pre-categorized files ready for instant 1-click import into **Zoho Books**, **QuickBooks**, or **Xero**.

---

## 💡 Why LedgerBridge? (The Problem It Solves)

If you have ever clicked **"Import Statement"** inside accounting software like Zoho Books, QuickBooks, or Xero, you probably noticed a frustrating reality:

1. **The "Uncategorized" Bottleneck**:  
   Accounting software does **not** know what your bank narrations mean. Uploading a raw bank statement simply dumps 200+ rows into an "Unmatched / Uncategorized" pile. A business owner or accountant must sit there and manually inspect every single line—clicking and choosing an account for `POS 4910283 WTH TRF`, `NIP/UBN/CHINEDU OKAFOR`, or `VAT MOBILE TRF`—every single month.
2. **Unsupported African / Nigerian Statement Formats**:  
   Nigerian banks (Access Bank, GTBank, Zenith Bank, First Bank) export complex, multi-page PDFs with summary headers, fee breakdowns, and branch stamps. Western accounting platforms fail to parse these tables accurately or reject them outright.
3. **No Running Arithmetic Verification**:  
   If a page was missed or an amount corrupted in an Excel export, standard software imports the flawed data without warning. Weeks later, month-end books are off by ₦35,420 and someone spends days combing through lines to find the error.
4. **Data Privacy & Compliance**:  
   Bank statements contain sensitive financial records, account numbers, and counterparty identities. Uploading raw statement text to third-party cloud AI APIs (like OpenAI or Anthropic) raises major data confidentiality, NDA, and regulatory compliance (NDPR/GDPR) concerns.

### The LedgerBridge Solution
LedgerBridge acts as a **smart pre-accounting intelligence layer**:
- 📥 **Drag-and-drop** digital bank PDFs (Access Bank supported out-of-the-box), Excel sheets (.xlsx), or CSVs.
- 📐 **Verifies running balance math** row-by-row (`Opening + Credits - Debits == Closing`), flagging the exact line if a bank statement is incomplete.
- ⚡ **2-Tier Hybrid Classification**:
  - **Tier 1 (Instant Rules)**: Deterministic keyword patterns classify standard merchants (telecoms, utilities, taxes, SaaS) in 0ms with zero AI compute.
  - **Tier 2 (Local Small Language Model)**: A lightweight, local AI model running 100% offline via **Ollama** (`qwen2.5-coder:1.5b`) infers ambiguous counterparties using structured JSON schemas.
- 🛡️ **Accounting Guardrails**: Deterministic sanity checks ensure accounting integrity (e.g. Income can never be a debit; Expense/COGS cannot be a credit).
- 🎯 **Human-in-the-Loop Review Queue**: Efficiently review only ambiguous or edge transactions (~9% on benchmark tests) with 1-click confirm dropdowns.
- 🔄 **Continuous Learning**: Every review resolution can be saved as a permanent rule and is injected as few-shot memory for future AI inferences.
- 📤 **Pre-Categorized Export**: Download a verified ledger with accounting categories already mapped, ready for seamless import into Zoho Books or Excel.

---

## 📊 Evaluation & Benchmark Results

LedgerBridge includes a built-in evaluation harness (`eval/run.py`) measuring accuracy, safety, and throughput against synthetic and hand-labeled benchmark statements (`eval/data/`):

| Configuration | Tier 1 (Rules) | Tier 2 (LLM) | Needs Review | Auto-Accept Error Rate | Macro-F1 | Throughput |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **A: Rules Only** | 79.1% | - | 20.9% | 2.94% | 88.9% | ~32,000 rows/s |
| **B: LLM Only (No Rules)** | - | 100.0% | 0.0% | 9.30% | 49.2% | ~94,000 rows/s |
| **C: Rules + LLM (Zero-Shot)** | 79.1% | 20.9% | 0.0% | 4.65% | 95.9% | ~44,000 rows/s |
| **D: Rules + LLM + Few-Shot** | 79.1% | 20.9% | 0.0% | 4.65% | 95.9% | ~46,000 rows/s |
| **E: Full System (Validators + Threshold)** | 72.1% | 18.6% | 9.3% | **0.0%** | 85.2% | ~34,000 rows/s |

> [!NOTE]
> **Safety First**: The primary objective of LedgerBridge is minimizing **Auto-Accept Error Rate** (preventing wrong categories from silently entering the general ledger). Config E achieves **0.0% false accepts** by routing borderline rows and guardrail violations to the human Review Queue.

---

## ⚠️ Known Limitations & Accounting Scope

### Known Limitations
- **Digital Text PDFs Only**: Scanned, photographed, or raster image PDFs without an underlying digital text stream are not parsed. (Run OCR before uploading scanned paper statements).
- **Supported Banks Tested**: Tested against statement formats from **Access Bank Plc**, **Guaranty Trust Bank (GTBank)**, and standard multi-column Excel/CSV bank exports.
- **Capitalization Threshold**: Distinguishing fixed assets from operational repairs relies on `CAPITALIZATION_THRESHOLD` (default: ₦500,000). Purchases below threshold are safely flagged for human confirmation.
- **Single-Narration Splitting**: Own-account transfers between company accounts and loan debt servicing (principal repayment vs. interest expense) appear as single debit lines on statements and cannot be split without supplementary amortization schedules.

### Accounting Scope
- **Cash-Basis Cash Movement**: A bank statement records solely the cash movement side of financial transactions. LedgerBridge prepares and classifies cash entries for your general ledger; full accrual accounting, deferred revenue recognition, and invoice-matching require cross-referencing your ERP or billing records.

---

## 🏛️ Financial Framework & Categories

LedgerBridge organizes transactions across the **5 Core Accounting Elements** and **8 Standard Operating Categories**:

1. **Assets**: Equipment, machinery, computing hardware $\ge$ ₦500k capitalization threshold.
2. **Liabilities**: Loan principal repayments, credit facility settlements.
3. **Income**: Client retainer fees, sales proceeds, consulting revenues.
4. **Expenses**: Utilities, telecoms, office supplies, travel, SaaS subscriptions, software licenses.
5. **Capital**: Owner equity contributions, shareholder capital injections.
6. **Cost of Goods Sold (COGS)**: Raw materials, manufacturing inventory, bulk packaging supplies.
7. **Internal Transfers**: Own-account sweeps, inter-bank liquidity rebalancing.
8. **Taxes & VAT**: Statutory FGN stamp duty, withholding tax (WHT), value-added tax charges.

---

## 🚀 Exporting and Importing into Accounting Software

LedgerBridge generates pre-categorized exports ready for import into **Zoho Books**, **QuickBooks**, **Xero**, or custom financial spreadsheets. *Note: Column mapping may be required depending on your accounting software configuration and chart of accounts.*

### Supported Export Formats & Exact Columns

#### 1. Clean Ledger (Flat Register CSV)
Exports the full transaction register with formula injection guards (cells beginning with `=`, `+`, `-`, or `@` in text columns are neutralized with a leading `'`).
- **`ID`**: Unique transaction identifier
- **`Date`**: Statement transaction date (`DD/MM/YYYY`)
- **`Value_Date`**: Value date (`DD/MM/YYYY`)
- **`Narration`**: Cleaned counterparty description
- **`Direction`**: `debit` or `credit`
- **`Amount`**: Transaction monetary value (positive float)
- **`Element`**: Categorized Chart of Accounts element (*Assets*, *Liabilities*, *Income*, *Expenses*, *Capital*, *Cost of Goods Sold*, *Internal Transfer*, *Taxes & VAT*, or *Needs Review*)
- **`Tier`**: Classification provenance (`rule`, `llm`, `user`, `validator`, or `ingestion`)
- **`Confidence`**: Classification confidence score (`0.0` to `1.0`)
- **`Status`**: Transaction status (`auto` or `reviewed`)

#### 2. Double-Entry Journal CSV
Balanced double-entry journal format designed for manual journal imports (e.g. Zoho Books Manual Journals).
> [!IMPORTANT]
> To preserve accounting integrity, journal export requires all transactions in the active statement to be confirmed. If any transactions remain in `Needs Review`, journal export is blocked until resolved in the Review Queue.
- **`Journal_Date`**: Transaction date
- **`Journal_Number`**: Unique journal sequence identifier (`JRN-XXXXXXXX`)
- **`Account_Name`**: Balanced double-entry account name (`Bank Account` vs classified Category Account)
- **`Debit`**: Debit line amount
- **`Credit`**: Credit line amount
- **`Description`**: Transaction narration

#### 3. Excel Audit Workbook (.xlsx)
Multi-sheet spreadsheet designed for financial controllers and auditors:
- **Sheet 1: `Categorized Rows`**: Full row-by-row transaction register.
- **Sheet 2: `5-Element Summary`**: Live Excel `=SUMIFS('Categorized Rows'!$F:$F, 'Categorized Rows'!$G:$G, A{row})` dynamic formulas calculating subtotals for each accounting element and a grand total.
- **Sheet 3: `Audit Log`**: Full classification audit trail recording classification tier, rule ID / model source, confidence score, resolution status, and validator demotion reasons.

---

## 🌟 Key Features

| Feature | Description |
| :--- | :--- |
| **100% Local & Offline AI** | Runs locally using Ollama (`qwen2.5-coder:1.5b`). No bank data, counterparties, or balances ever touch external cloud servers. |
| **Arithmetic Integrity Proof** | Validates the golden accounting formula: `Opening Balance + Inflows - Outflows == Closing Balance`. Shows instant pass/discrepancy badges. |
| **SHA-256 Deduplication** | Fingerprints each transaction row (`date + amount + normalized_narration + balance`). Upload overlapping statements without double-counting rows. |
| **Dynamic Chart of Accounts** | Includes 8 default categories (*Assets, Liabilities, Income, Expenses, Capital, Cost of Goods Sold, Internal Transfer, Taxes & VAT*) plus full UI support for custom business categories. |
| **Direction-Aware Guardrails** | Built-in accounting sanity checks prevent model hallucinations (e.g., flagging credit card debits mislabeled as income). |
| **Modern Desktop UI** | Fast React 19 + Tailwind CSS interface with persistent routing, collapsible navigation, password visibility toggles, and secure HttpOnly cookie authentication. |

---

## 🛠️ Quick Start

### 1. Prerequisites
- **Node.js**: v18+ & `npm`
- **Python**: v3.10+
- **Ollama**: [Download Ollama](https://ollama.ai) and pull the recommended lightweight model:
  ```bash
  ollama pull qwen2.5-coder:1.5b
  ```

### 2. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Reset and seed database with Access Bank & Excel demo fixtures
python seed_db.py

# Start FastAPI server (runs on http://127.0.0.1:8000)
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Frontend Setup
```bash
# In a new terminal, navigate to frontend directory
cd frontend

# Install packages
npm install

# Start Vite dev server (runs on http://localhost:5173)
npm run dev
```

### 4. Log In
Open `http://localhost:5173` in your browser and sign in with the default seeded account:
- **Email**: `finance@company.com`
- **Password**: `SecurePassword123!`

---

## 🔬 System Architecture & AI Engineering

For a comprehensive technical breakdown of our **2-tier hybrid classification pipeline**, **structured JSON schema enforcement**, **in-context few-shot learning from SQLite overrides**, and **graceful fallback architecture**, read the full technical specification:

👉 [**System Architecture & AI Engineering Blueprint (`architecture.md`)**](./architecture.md)

---

## 📄 License
MIT License. Developed for privacy-first, professional bookkeeping automation.
