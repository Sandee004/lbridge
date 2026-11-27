import csv
import datetime
import hashlib
import io
import re
from decimal import Decimal, InvalidOperation
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union
import openpyxl


def clean_decimal(val_any: Any) -> Decimal:
    """Converts a raw value (number, string with currency/commas, or None) into Decimal."""
    if val_any is None:
        return Decimal("0.00")
    if isinstance(val_any, (int, float, Decimal)):
        return Decimal(str(val_any))
    s = str(val_any).strip()
    if s in ["-", "--", "", "None", "nil", "N/A", "Nil", "nan"]:
        return Decimal("0.00")
    is_neg = "-" in s or "DR" in s.upper() or (s.startswith("(") and s.endswith(")"))
    cleaned = re.sub(r"[^\d.]", "", s)
    if not cleaned:
        return Decimal("0.00")
    try:
        val = Decimal(cleaned)
        return -val if is_neg else val
    except InvalidOperation:
        return Decimal("0.00")


def normalize_date_str(val_any: Any) -> str:
    """Normalizes any date object or date string into DD/MM/YYYY format."""
    if isinstance(val_any, (datetime.date, datetime.datetime)):
        return val_any.strftime("%d/%m/%Y")
    s = str(val_any).strip()
    # YYYY-MM-DD
    m_iso = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m_iso:
        y, m, d = m_iso.groups()
        return f"{int(d):02d}/{int(m):02d}/{y}"
    # DD/MM/YYYY or MM/DD/YYYY
    m_slash = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})", s)
    if m_slash:
        p1, p2, yr = m_slash.groups()
        if len(yr) == 2:
            yr = f"20{yr}"
        return f"{int(p1):02d}/{int(p2):02d}/{yr}"
    return s


def generate_fingerprint(date_str: str, amount: float, direction: str, desc_norm: str, balance: Optional[float]) -> str:
    """Computes a unique SHA-256 fingerprint for deduplicating transactions."""
    bal_str = f"{balance:.2f}" if balance is not None else "nobal"
    raw = f"{date_str}|{amount:.2f}|{direction}|{desc_norm}|{bal_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_excel_or_csv_statement(
    file_input: Union[str, bytes, BinaryIO],
    filename: str = "statement.xlsx"
) -> Dict[str, Any]:
    """
    Parses a bank statement in Excel (.xlsx, .xls) or CSV format.
    Automatically discovers columns (Date, Description, Debit, Credit, Balance),
    calculates arithmetic totals, checks math consistency, and deduplicates via SHA-256.
    """
    ext = filename.lower().split(".")[-1] if "." in filename else "xlsx"

    # Read rows into list of list of cells
    raw_rows: List[List[Any]] = []

    if ext == "csv":
        if isinstance(file_input, str):
            with open(file_input, "r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.reader(f)
                raw_rows = [row for row in reader]
        elif isinstance(file_input, bytes):
            text = file_input.decode("utf-8-sig", errors="ignore")
            reader = csv.reader(io.StringIO(text))
            raw_rows = [row for row in reader]
        else:
            text = file_input.read().decode("utf-8-sig", errors="ignore")
            reader = csv.reader(io.StringIO(text))
            raw_rows = [row for row in reader]
    else:
        # Excel (.xlsx) via openpyxl
        wb_stream = io.BytesIO(file_input) if isinstance(file_input, bytes) else file_input
        wb = openpyxl.load_workbook(wb_stream, data_only=True)
        sheet = wb.active
        for row in sheet.iter_rows(values_only=True):
            raw_rows.append(list(row))

    if not raw_rows:
        raise ValueError("The uploaded Excel/CSV file is empty.")

    # -------------------------------------------------------------
    # 1. Detect Metadata in Header Rows (Bank name, Period, Currency)
    # -------------------------------------------------------------
    bank_name = "Generic Bank"
    currency = "NGN"
    period_start = None
    period_end = None
    opening_balance_hdr: Optional[Decimal] = None
    closing_balance_hdr: Optional[Decimal] = None

    header_text_combined = ""
    for r in raw_rows[:15]:
        row_str = " ".join(str(c) for c in r if c is not None)
        header_text_combined += " " + row_str

    if re.search(r"\baccess\b|\baccess bank\b", header_text_combined, re.I):
        bank_name = "Access Bank Plc"
    elif re.search(r"\bgtbank\b|\bguaranty trust\b", header_text_combined, re.I):
        bank_name = "Guaranty Trust Bank (GTBank)"
    elif re.search(r"\bzenith\b", header_text_combined, re.I):
        bank_name = "Zenith Bank Plc"
    elif re.search(r"\bstanbic\b", header_text_combined, re.I):
        bank_name = "Stanbic IBTC Bank"

    if "USD" in header_text_combined or "$" in header_text_combined:
        currency = "USD"
    elif "GBP" in header_text_combined or "£" in header_text_combined:
        currency = "GBP"
    elif "EUR" in header_text_combined or "€" in header_text_combined:
        currency = "EUR"
    else:
        currency = "NGN"

    # Extract dates from header
    p_m = re.search(r"(\d{1,2}/\d{1,2}/\d{4})\s*[-to]+\s*(\d{1,2}/\d{1,2}/\d{4})", header_text_combined, re.I)
    if p_m:
        period_start, period_end = p_m.group(1), p_m.group(2)

    # -------------------------------------------------------------
    # 2. Locate the Column Header Row
    # -------------------------------------------------------------
    date_col = None
    desc_col = None
    debit_col = None
    credit_col = None
    balance_col = None
    amount_col = None
    type_col = None
    header_row_idx = None

    for idx, row in enumerate(raw_rows[:30]):
        row_lower = [str(c).strip().lower() if c is not None else "" for c in row]

        has_date = any(k in cell for cell in row_lower for k in ["date", "post date", "txn date", "trans date", "value date"])
        has_desc = any(k in cell for cell in row_lower for k in ["narration", "description", "particulars", "memo", "details"])
        has_amount = any(k in cell for cell in row_lower for k in ["debit", "credit", "withdrawal", "deposit", "amount"])

        if has_date and (has_desc or has_amount):
            header_row_idx = idx
            for col_idx, cell in enumerate(row_lower):
                if not cell:
                    continue
                if any(k in cell for k in ["post date", "trans date", "txn date", "date"]) and date_col is None:
                    date_col = col_idx
                elif any(k in cell for k in ["narration", "description", "particulars", "memo", "details"]):
                    desc_col = col_idx
                elif any(k in cell for k in ["debit", "withdrawal", "money out", "dr"]):
                    debit_col = col_idx
                elif any(k in cell for k in ["credit", "deposit", "money in", "cr"]):
                    credit_col = col_idx
                elif any(k in cell for k in ["balance", "bal", "running"]):
                    balance_col = col_idx
                elif "amount" in cell and amount_col is None:
                    amount_col = col_idx
                elif any(k in cell for k in ["type", "dr/cr"]):
                    type_col = col_idx
            break

    if header_row_idx is None or (date_col is None and desc_col is None):
        raise ValueError(
            "Could not identify statement table columns in the Excel/CSV file. "
            "Ensure the sheet contains Date and Narration/Description columns."
        )

    # -------------------------------------------------------------
    # 3. Parse Data Rows
    # -------------------------------------------------------------
    raw_txns: List[Dict[str, Any]] = []

    for row_idx in range(header_row_idx + 1, len(raw_rows)):
        row = raw_rows[row_idx]
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue

        raw_date = row[date_col] if date_col is not None and date_col < len(row) else None
        if raw_date is None or str(raw_date).strip() == "":
            continue

        date_str = normalize_date_str(raw_date)

        # Ignore total / summary rows at bottom
        first_cell_str = str(row[0] if len(row) > 0 and row[0] is not None else "").lower()
        if any(k in first_cell_str for k in ["total", "summary", "closing balance", "page"]):
            continue

        raw_desc = str(row[desc_col] if desc_col is not None and desc_col < len(row) and row[desc_col] is not None else "UNSPECIFIED")
        desc_clean = re.sub(r"\s+", " ", raw_desc).strip()
        desc_norm = desc_clean.lower()

        # Amounts
        deb_val = Decimal("0.00")
        cr_val = Decimal("0.00")

        if debit_col is not None and debit_col < len(row):
            deb_val = clean_decimal(row[debit_col])
        if credit_col is not None and credit_col < len(row):
            cr_val = clean_decimal(row[credit_col])

        # If single amount column with Type or signed values
        if deb_val == Decimal("0.00") and cr_val == Decimal("0.00") and amount_col is not None and amount_col < len(row):
            raw_amt = clean_decimal(row[amount_col])
            txn_type = str(row[type_col]).upper() if type_col is not None and type_col < len(row) and row[type_col] else ""
            if "DR" in txn_type or raw_amt < Decimal("0.00"):
                deb_val = abs(raw_amt)
            else:
                cr_val = abs(raw_amt)

        bal_val = Decimal("0.00")
        if balance_col is not None and balance_col < len(row):
            bal_val = clean_decimal(row[balance_col])

        if cr_val > Decimal("0.00"):
            direction = "credit"
            amount_val = cr_val
        else:
            direction = "debit"
            amount_val = deb_val

        # Skip rows with no amount
        if amount_val == Decimal("0.00"):
            continue

        raw_txns.append({
            "date": date_str,
            "description_raw": desc_clean,
            "description_norm": desc_norm,
            "debit": deb_val,
            "credit": cr_val,
            "amount": amount_val,
            "direction": direction,
            "balance": bal_val,
        })

    if not raw_txns:
        raise ValueError(
            "No transactions could be parsed from this Excel/CSV statement. "
            "Please ensure it contains a recognizable transaction table with dates, descriptions, and amounts."
        )

    # -------------------------------------------------------------
    # 4. Arithmetic Verification
    # -------------------------------------------------------------
    first_txn = raw_txns[0]
    last_txn = raw_txns[-1]

    opening_balance = opening_balance_hdr
    if opening_balance is None and first_txn["balance"] != Decimal("0.00"):
        opening_balance = first_txn["balance"] + first_txn["debit"] - first_txn["credit"]

    closing_balance = closing_balance_hdr
    if closing_balance is None and last_txn["balance"] != Decimal("0.00"):
        closing_balance = last_txn["balance"]

    balances_found = (opening_balance is not None and closing_balance is not None)

    if opening_balance is None:
        opening_balance = Decimal("0.00")
    if closing_balance is None:
        closing_balance = Decimal("0.00")

    running_calc = opening_balance
    calc_total_credits = Decimal("0.00")
    calc_total_debits = Decimal("0.00")
    math_ok = True
    math_error_detail: Optional[str] = None

    if not balances_found:
        math_ok = False
        math_error_detail = "Could not verify: balances not found"
    else:
        for r_idx, txn in enumerate(raw_txns):
            calc_total_credits += txn["credit"]
            calc_total_debits += txn["debit"]
            running_calc = running_calc - txn["debit"] + txn["credit"]

            if txn["balance"] != Decimal("0.00"):
                diff = abs(running_calc - txn["balance"])
                if diff > Decimal("0.01"):
                    math_ok = False
                    math_error_detail = (
                        f"Arithmetic discrepancy at row {r_idx + 1} ({txn['date']} - {txn['description_raw'][:30]}): "
                        f"expected balance was {running_calc:,.2f}, but sheet shows {txn['balance']:,.2f}."
                    )
                    break

        if math_ok and closing_balance != Decimal("0.00"):
            diff_close = abs(running_calc - closing_balance)
            if diff_close > Decimal("0.01"):
                math_ok = False
                math_error_detail = (
                    f"Closing balance mismatch: computed final is {running_calc:,.2f}, but sheet indicates {closing_balance:,.2f}."
                )

    processed_transactions = []
    for txn in raw_txns:
        fp = generate_fingerprint(
            date_str=txn["date"],
            amount=float(txn["amount"]),
            direction=txn["direction"],
            desc_norm=txn["description_norm"],
            balance=float(txn["balance"]) if txn["balance"] != Decimal("0.00") else None,
        )
        processed_transactions.append({
            "date": txn["date"],
            "value_date": txn["date"],
            "description_raw": txn["description_raw"],
            "description_norm": txn["description_norm"],
            "amount": float(txn["amount"]),
            "direction": txn["direction"],
            "balance": float(txn["balance"]) if txn["balance"] != Decimal("0.00") else None,
            "fingerprint": fp,
            "element": "needs_review",
            "tier": "ingestion",
            "confidence": 0.0,
            "reason": "Parsed from Excel/CSV statement",
            "status": "auto",
        })

    if not period_start and raw_txns:
        period_start = raw_txns[0]["date"]
    if not period_end and raw_txns:
        period_end = raw_txns[-1]["date"]

    return {
        "filename": filename,
        "bank_name": bank_name,
        "currency": currency,
        "period_start": period_start,
        "period_end": period_end,
        "opening_balance": float(opening_balance),
        "closing_balance": float(closing_balance if closing_balance != Decimal("0.00") else running_calc),
        "total_credits": float(calc_total_credits),
        "total_debits": float(calc_total_debits),
        "math_ok": math_ok,
        "math_error_detail": math_error_detail,
        "transaction_count": len(processed_transactions),
        "transactions": processed_transactions,
    }
