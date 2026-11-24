import hashlib
import io
import re
from decimal import Decimal, InvalidOperation
from typing import Any, BinaryIO, Dict, List, Optional, Union
import pypdf


def clean_decimal(val_str: Optional[str]) -> Decimal:
    """Converts a raw currency string (e.g. '₦1,200.50', '25,000.00', or '-') into a Decimal."""
    if not val_str:
        return Decimal("0.00")
    s = val_str.strip()
    if s in ["-", "--", "", "None", "nil", "N/A", "Nil"]:
        return Decimal("0.00")
    is_neg = "-" in s or "DR" in s
    cleaned = re.sub(r"[^\d.]", "", s)
    if not cleaned:
        return Decimal("0.00")
    try:
        val = Decimal(cleaned)
        return -val if is_neg else val
    except InvalidOperation:
        return Decimal("0.00")


def generate_fingerprint(date_str: str, amount: float, direction: str, desc_norm: str, balance: Optional[float]) -> str:
    """Computes a unique SHA-256 fingerprint for deduplicating transactions."""
    bal_str = f"{balance:.2f}" if balance is not None else "nobal"
    raw = f"{date_str}|{amount:.2f}|{direction}|{desc_norm}|{bal_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_pdf_statement(file_input: Union[str, bytes, BinaryIO], filename: str = "statement.pdf") -> Dict[str, Any]:
    """
    Parses digital text-based Nigerian and generic bank statement PDFs (Access Bank, GTBank, Zenith, etc.).
    Extracts header metadata (Bank Name, Period, Opening/Closing Balances),
    all transaction line items, and performs complete arithmetic verification.
    """
    if isinstance(file_input, str):
        reader = pypdf.PdfReader(file_input)
    elif isinstance(file_input, bytes):
        reader = pypdf.PdfReader(io.BytesIO(file_input))
    else:
        reader = pypdf.PdfReader(file_input)

    if len(reader.pages) == 0:
        raise ValueError("The provided PDF file has 0 pages.")

    footer_patterns = [
        r"Page\s+\d+\s+of\s+\d+",
        r"This report indicates transaction details",
        r"contactcenter@accessbankplc\.com",
        r"CONFIDENTIAL",
        r"OFFICIAL ACCOUNT STATEMENT",
    ]

    all_lines: List[str] = []
    total_chars = 0

    for page in reader.pages:
        page_text = page.extract_text() or ""
        total_chars += len(page_text.strip())
        for raw_line in page_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if any(re.search(pat, line, re.IGNORECASE) for pat in footer_patterns):
                continue
            all_lines.append(line)

    if total_chars < 50:
        raise ValueError(
            "This PDF appears to be a scanned image or empty. "
            "Please upload a digital text-based PDF statement. (OCR is not supported in MVP)."
        )

    full_text = " ".join(all_lines)

    # -------------------------------------------------------------
    # 1. Identify Bank Name & Currency
    # -------------------------------------------------------------
    bank_name = "Generic Bank"
    if re.search(r"\baccess\b|\baccess bank\b", full_text, re.IGNORECASE):
        bank_name = "Access Bank Plc"
    elif re.search(r"\bgtbank\b|\bguaranty trust\b", full_text, re.IGNORECASE):
        bank_name = "Guaranty Trust Bank (GTBank)"
    elif re.search(r"\bzenith\b|\bzenith bank\b", full_text, re.IGNORECASE):
        bank_name = "Zenith Bank Plc"
    elif re.search(r"\bstanbic\b", full_text, re.IGNORECASE):
        bank_name = "Stanbic IBTC Bank"
    elif re.search(r"\bkuda\b", full_text, re.IGNORECASE):
        bank_name = "Kuda Microfinance Bank"
    elif re.search(r"\bmoniepoint\b", full_text, re.IGNORECASE):
        bank_name = "Moniepoint MFB"

    currency = "NGN" if ("NGN" in full_text or "₦" in full_text or "NAIRA" in full_text.upper()) else "USD"

    # -------------------------------------------------------------
    # 2. Extract Period Start and End
    # -------------------------------------------------------------
    period_start = None
    period_end = None
    p_m = re.search(r"(\d{2}/\d{2}/\d{4})\s*[-to]+\s*(\d{2}/\d{2}/\d{4})", full_text, re.IGNORECASE)
    if p_m:
        period_start, period_end = p_m.group(1), p_m.group(2)
    else:
        p_dash = re.search(r"(\d{4}-\d{2}-\d{2})\s*[-to]+\s*(\d{4}-\d{2}-\d{2})", full_text, re.IGNORECASE)
        if p_dash:
            period_start, period_end = p_dash.group(1), p_dash.group(2)

    # -------------------------------------------------------------
    # 3. Extract Opening & Closing Balance Summary
    # -------------------------------------------------------------
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    total_credits: Optional[Decimal] = None
    total_debits: Optional[Decimal] = None

    # Pattern A: Access Bank "Overview / Retail Accounts" summary block
    for i, line in enumerate(all_lines[:60]):
        if "Account No" in line and i + 13 < len(all_lines):
            if "Debits" in all_lines[i + 4] and "Credits" in all_lines[i + 5]:
                opening_balance = clean_decimal(all_lines[i + 10])
                total_debits = clean_decimal(all_lines[i + 11])
                total_credits = clean_decimal(all_lines[i + 12])
                closing_balance = clean_decimal(all_lines[i + 13])
                break

    # Pattern B: Standard key-value pairs (Opening Balance: X, Closing Balance: Y)
    if opening_balance is None:
        for line in all_lines[:40]:
            if "Opening Balance" in line:
                m = re.search(r"Opening Balance[:\s]*([₦\$£€]?\s*[\d,]+\.\d{2})", line, re.IGNORECASE)
                if m:
                    opening_balance = clean_decimal(m.group(1))
            if "Closing Balance" in line:
                m = re.search(r"Closing Balance[:\s]*([₦\$£€]?\s*[\d,]+\.\d{2})", line, re.IGNORECASE)
                if m:
                    closing_balance = clean_decimal(m.group(1))

    # -------------------------------------------------------------
    # 4. Extract Transactions (Access Bank & Generic layouts)
    # -------------------------------------------------------------
    date_regex = re.compile(r"^(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2}|\d{2}-[A-Za-z]{3}-\d{4})$")
    amount_regex = re.compile(r"^[₦\$£€]?\s*[\d,]+\.\d{2}$|^-$")
    table_headers = {
        "post date", "value date", "date", "narration", "description", "ref/cheque no.",
        "debits", "credits", "balance", "debit ($)", "credit ($)", "balance ($)",
        "withdrawal", "deposit", "withdrawals (debit)", "deposits (credit)"
    }

    raw_transactions: List[Dict[str, Any]] = []
    idx = 0
    num_lines = len(all_lines)

    while idx < num_lines:
        line = all_lines[idx]

        if line.lower() in table_headers:
            idx += 1
            continue

        # Access Bank format: Post Date immediately followed by Value Date
        if date_regex.match(line) and idx + 1 < num_lines and date_regex.match(all_lines[idx + 1]):
            post_date = line
            value_date = all_lines[idx + 1]
            idx += 2

            tokens = []
            while idx < num_lines:
                curr = all_lines[idx]
                if curr.lower() in table_headers:
                    idx += 1
                    continue
                # If next transaction dates are reached, break
                if date_regex.match(curr) and idx + 1 < num_lines and date_regex.match(all_lines[idx + 1]):
                    break
                tokens.append(curr)
                idx += 1
                # When tokens contains at least 3 amount items at the end
                if len(tokens) >= 4 and all(amount_regex.match(t) for t in tokens[-3:]):
                    if clean_decimal(tokens[-1]) != Decimal("0.00") or tokens[-1] != "-":
                        break

            if len(tokens) >= 3:
                debit_str = tokens[-3]
                credit_str = tokens[-2]
                bal_str = tokens[-1]
                desc_tokens = tokens[:-3]

                deb_val = clean_decimal(debit_str)
                cr_val = clean_decimal(credit_str)
                bal_val = clean_decimal(bal_str)

                description_raw = " ".join(desc_tokens).strip() or "UNSPECIFIED TRANSACTION"
                description_norm = re.sub(r"\s+", " ", description_raw).strip().lower()

                if cr_val > Decimal("0.00"):
                    direction = "credit"
                    amount_val = cr_val
                else:
                    direction = "debit"
                    amount_val = deb_val

                raw_transactions.append({
                    "date": post_date,
                    "value_date": value_date,
                    "description_raw": description_raw,
                    "description_norm": description_norm,
                    "debit": deb_val,
                    "credit": cr_val,
                    "amount": amount_val,
                    "direction": direction,
                    "balance": bal_val,
                })

        # Generic format: Single Date column
        elif date_regex.match(line):
            date_str = line
            idx += 1

            desc_tokens = []
            while idx < num_lines:
                curr = all_lines[idx]
                if curr.lower() in table_headers:
                    idx += 1
                    continue
                if date_regex.match(curr):
                    break
                if amount_regex.match(curr) and idx + 1 < num_lines and amount_regex.match(all_lines[idx + 1]):
                    break
                desc_tokens.append(curr)
                idx += 1
                if len(desc_tokens) >= 4:
                    break

            description_raw = " ".join(desc_tokens).strip() or "UNSPECIFIED TRANSACTION"
            description_norm = re.sub(r"\s+", " ", description_raw).strip().lower()

            debit_str = all_lines[idx] if idx < num_lines else "-"
            idx += 1
            credit_str = all_lines[idx] if idx < num_lines else "-"
            idx += 1
            balance_str = all_lines[idx] if idx < num_lines else "-"
            idx += 1

            deb_val = clean_decimal(debit_str)
            cr_val = clean_decimal(credit_str)
            bal_val = clean_decimal(balance_str)

            if cr_val > Decimal("0.00"):
                direction = "credit"
                amount_val = cr_val
            else:
                direction = "debit"
                amount_val = deb_val

            raw_transactions.append({
                "date": date_str,
                "value_date": date_str,
                "description_raw": description_raw,
                "description_norm": description_norm,
                "debit": deb_val,
                "credit": cr_val,
                "amount": amount_val,
                "direction": direction,
                "balance": bal_val,
            })
        else:
            idx += 1

    # -------------------------------------------------------------
    # 5. Arithmetic Verification
    # -------------------------------------------------------------
    if raw_transactions:
        first_txn = raw_transactions[0]
        last_txn = raw_transactions[-1]

        if opening_balance is None and first_txn["balance"] != Decimal("0.00"):
            opening_balance = first_txn["balance"] + first_txn["debit"] - first_txn["credit"]

        if closing_balance is None and last_txn["balance"] != Decimal("0.00"):
            closing_balance = last_txn["balance"]

    if opening_balance is None:
        opening_balance = Decimal("0.00")
    if closing_balance is None:
        closing_balance = Decimal("0.00")

    running_calc = opening_balance
    calc_total_credits = Decimal("0.00")
    calc_total_debits = Decimal("0.00")
    math_ok = True
    math_error_detail: Optional[str] = None

    for r_idx, txn in enumerate(raw_transactions):
        calc_total_credits += txn["credit"]
        calc_total_debits += txn["debit"]
        running_calc = running_calc - txn["debit"] + txn["credit"]

        if txn["balance"] != Decimal("0.00"):
            diff = abs(running_calc - txn["balance"])
            if diff > Decimal("0.01"):
                math_ok = False
                math_error_detail = (
                    f"Arithmetic discrepancy at row {r_idx + 1} ({txn['date']} - {txn['description_raw'][:35]}): "
                    f"expected balance was ₦{running_calc:,.2f}, but statement shows ₦{txn['balance']:,.2f}."
                )
                break

    if math_ok and closing_balance != Decimal("0.00"):
        diff_close = abs(running_calc - closing_balance)
        if diff_close > Decimal("0.01"):
            math_ok = False
            math_error_detail = (
                f"Closing balance mismatch: opening (₦{opening_balance:,.2f}) + credits (₦{calc_total_credits:,.2f}) "
                f"- debits (₦{calc_total_debits:,.2f}) = ₦{running_calc:,.2f}, but statement specifies ₦{closing_balance:,.2f}."
            )

    processed_transactions = []
    for txn in raw_transactions:
        fp = generate_fingerprint(
            date_str=txn["date"],
            amount=float(txn["amount"]),
            direction=txn["direction"],
            desc_norm=txn["description_norm"],
            balance=float(txn["balance"]) if txn["balance"] != Decimal("0.00") else None,
        )
        processed_transactions.append({
            "date": txn["date"],
            "value_date": txn.get("value_date", txn["date"]),
            "description_raw": txn["description_raw"],
            "description_norm": txn["description_norm"],
            "amount": float(txn["amount"]),
            "direction": txn["direction"],
            "balance": float(txn["balance"]) if txn["balance"] != Decimal("0.00") else None,
            "fingerprint": fp,
            "element": "needs_review",
            "tier": "ingestion",
            "confidence": 0.0,
            "reason": "Parsed from Access Bank statement",
            "status": "auto",
        })

    return {
        "filename": filename,
        "bank_name": bank_name,
        "currency": currency,
        "period_start": period_start,
        "period_end": period_end,
        "opening_balance": float(opening_balance),
        "closing_balance": float(closing_balance),
        "total_credits": float(total_credits if total_credits is not None else calc_total_credits),
        "total_debits": float(total_debits if total_debits is not None else calc_total_debits),
        "math_ok": math_ok,
        "math_error_detail": math_error_detail,
        "transaction_count": len(processed_transactions),
        "transactions": processed_transactions,
    }
