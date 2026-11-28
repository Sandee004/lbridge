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
    if cleaned.count(".") > 1:
        # Handles bank statement report typos with multiple periods e.g. 6,481.769.21 -> 6481769.21
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        val = Decimal(cleaned)
        return -val if is_neg else val
    except InvalidOperation:
        return Decimal("0.00")


def generate_fingerprint(
    date_str: str,
    amount: float,
    direction: str,
    desc_norm: str,
    balance: Optional[float] = None,
    ref: Optional[str] = None,
) -> str:
    """Computes a unique SHA-256 fingerprint for deduplicating transactions."""
    bal_str = f"{balance:.2f}" if balance is not None else "nobal"
    ref_str = f"|ref:{ref.strip()}" if ref and ref.strip() else ""
    raw = f"{date_str}|{amount:.2f}|{direction}|{desc_norm}|{bal_str}{ref_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _detect_bank_name(header_text: str, full_text: str) -> str:
    """Detects bank name from statement header text, falling back to full text if needed."""
    bank_patterns = [
        (r"\bzenith\b|\bzenith bank\b", "Zenith Bank Plc"),
        (r"\baccess\b|\baccess bank\b", "Access Bank Plc"),
        (r"\bgtbank\b|\bguaranty trust\b", "Guaranty Trust Bank (GTBank)"),
        (r"\bfirst bank\b|\bfirstbank\b", "First Bank of Nigeria"),
        (r"\buba\b|\bunited bank for africa\b", "United Bank for Africa (UBA)"),
        (r"\bstanbic\b", "Stanbic IBTC Bank"),
        (r"\bfidelity\b|\bfidelity bank\b", "Fidelity Bank Plc"),
        (r"\bkuda\b", "Kuda Microfinance Bank"),
        (r"\bmoniepoint\b", "Moniepoint MFB"),
        (r"\bpalmpay\b", "PalmPay"),
        (r"\bsterling\b", "Sterling Bank"),
        (r"\bwema\b|\balat\b", "Wema Bank / ALAT"),
        (r"\bpolaris\b", "Polaris Bank"),
        (r"\bunion bank\b|\buniononline\b", "Union Bank of Nigeria"),
        (r"\bfcmb\b|\bfirst city monument\b", "FCMB"),
        (r"\becobank\b", "Ecobank Nigeria"),
    ]
    # Check top-of-statement header text first to avoid false matches on counterparty narrations
    for pat, name in bank_patterns:
        if re.search(pat, header_text, re.IGNORECASE):
            return name
    # Fallback to full text if header check didn't match
    for pat, name in bank_patterns:
        if re.search(pat, full_text, re.IGNORECASE):
            return name
    return "Generic Bank"


def _parse_palmpay_pdf(reader: pypdf.PdfReader, filename: str) -> Dict[str, Any]:
    """
    Parser for PalmPay digital account statement PDFs.
    Extracts timestamped transactions across multi-page statements, handles signed amounts (+/-),
    and validates Money In / Money Out statement totals.
    """
    full_first_pages = " ".join(page.extract_text() or "" for page in reader.pages[:3])

    period_start, period_end = None, None
    m_period = re.search(
        r"Statement Period\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})",
        full_first_pages,
        re.IGNORECASE,
    )
    if m_period:
        p_start_raw = m_period.group(1).split("/")
        p_end_raw = m_period.group(2).split("/")
        period_start = f"{p_start_raw[1]}/{p_start_raw[0]}/{p_start_raw[2]}" if len(p_start_raw) == 3 else m_period.group(1)
        period_end = f"{p_end_raw[1]}/{p_end_raw[0]}/{p_end_raw[2]}" if len(p_end_raw) == 3 else m_period.group(2)

    expected_money_in = Decimal("0.00")
    expected_money_out = Decimal("0.00")
    m_in = re.search(r"Total Money In\s*[₦\$£€]?\s*([\d,.]+\.\d{2})", full_first_pages, re.IGNORECASE)
    if m_in:
        expected_money_in = clean_decimal(m_in.group(1))
    m_out = re.search(r"Total Money Out\s*[₦\$£€]?\s*([\d,.]+\.\d{2})", full_first_pages, re.IGNORECASE)
    if m_out:
        expected_money_out = clean_decimal(m_out.group(1))

    date_time_re = re.compile(r"^(\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+[AP]M)\s*(.*)$")
    amt_re = re.compile(r"([+-]\d+(?:\.\d{2})?)\s+([a-zA-Z0-9_-]+)")

    calc_total_credits = Decimal("0.00")
    calc_total_debits = Decimal("0.00")
    processed_transactions: List[Dict[str, Any]] = []

    curr_date = None
    curr_tokens: List[str] = []

    def commit_palmpay_txn(dt: Optional[str], tokens: List[str]):
        nonlocal calc_total_credits, calc_total_debits
        if not dt or not tokens:
            return
        full_line = " ".join(tokens)
        m_amt = amt_re.search(full_line)
        if not m_amt:
            return
        amt_str = m_amt.group(1)
        tx_id = m_amt.group(2)
        desc = full_line[: m_amt.start()].strip() or "PALMPAY TRANSACTION"
        amt_val = clean_decimal(amt_str)

        if amt_val > Decimal("0.00"):
            calc_total_credits += amt_val
            direction = "credit"
            cr = amt_val
            dr = Decimal("0.00")
        else:
            calc_total_debits += abs(amt_val)
            direction = "debit"
            cr = Decimal("0.00")
            dr = abs(amt_val)

        dt_parts = dt.split()[0].split("/")
        std_date = f"{dt_parts[1]}/{dt_parts[0]}/{dt_parts[2]}" if len(dt_parts) == 3 else dt

        desc_norm = re.sub(r"\s+", " ", desc).strip().lower()
        fp = generate_fingerprint(
            date_str=std_date,
            amount=float(abs(amt_val)),
            direction=direction,
            desc_norm=desc_norm,
            balance=None,
            ref=tx_id,
        )

        processed_transactions.append({
            "date": std_date,
            "value_date": std_date,
            "description_raw": desc,
            "description_norm": desc_norm,
            "amount": float(abs(amt_val)),
            "direction": direction,
            "balance": None,
            "fingerprint": fp,
            "element": "needs_review",
            "tier": "ingestion",
            "confidence": 0.0,
            "reason": "Parsed from PalmPay statement",
            "status": "auto",
            "ref": tx_id,
        })

    for page in reader.pages:
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if re.match(r"^\d{1,3}$", line):
                continue
            if any(
                h in line
                for h in [
                    "Account Statement",
                    "Total Money In",
                    "Total Money Out",
                    "Transaction Date Transaction Detail",
                    "Print Time",
                    "Page:",
                ]
            ):
                continue
            if (
                line.startswith("Name ")
                or line.startswith("Phone Number")
                or line.startswith("Account Number")
            ):
                continue

            m_start = date_time_re.match(line)
            if m_start:
                commit_palmpay_txn(curr_date, curr_tokens)
                curr_date = m_start.group(1)
                curr_tokens = [m_start.group(2)] if m_start.group(2) else []
            elif curr_date:
                curr_tokens.append(line)

    commit_palmpay_txn(curr_date, curr_tokens)

    math_ok = True
    math_error_detail = None
    if expected_money_in > Decimal("0.00") or expected_money_out > Decimal("0.00"):
        diff_in = abs(calc_total_credits - expected_money_in)
        diff_out = abs(calc_total_debits - expected_money_out)
        if diff_in > Decimal("0.05") or diff_out > Decimal("0.05"):
            math_ok = False
            math_error_detail = (
                f"PalmPay total mismatch: Money In (expected ₦{expected_money_in:,.2f}, got ₦{calc_total_credits:,.2f}), "
                f"Money Out (expected ₦{expected_money_out:,.2f}, got ₦{calc_total_debits:,.2f})"
            )

    return {
        "filename": filename,
        "bank_name": "PalmPay",
        "currency": "NGN",
        "period_start": period_start,
        "period_end": period_end,
        "opening_balance": 0.0,
        "closing_balance": float(calc_total_credits - calc_total_debits),
        "total_credits": float(expected_money_in if expected_money_in > 0 else calc_total_credits),
        "total_debits": float(expected_money_out if expected_money_out > 0 else calc_total_debits),
        "math_ok": math_ok,
        "math_error_detail": math_error_detail,
        "transaction_count": len(processed_transactions),
        "transactions": processed_transactions,
    }


def _parse_tabular_layout_pdf(reader: pypdf.PdfReader, filename: str) -> Optional[Dict[str, Any]]:
    """
    Universal multi-column tabular parser for digital bank statement PDFs.
    Works for Zenith Bank, Access Bank, GTBank, Fidelity Bank, First Bank, UBA, Stanbic IBTC, etc.
    Dynamically maps amounts to columns (Debit, Credit, Balance) using Euclidean column-center distance,
    correctly associates wrapped narrations, cleans overlays, and verifies arithmetic.
    """
    first_page_header = (reader.pages[0].extract_text() or "")[:1000]
    full_text = " ".join(page.extract_text() or "" for page in reader.pages)

    bank_name = _detect_bank_name(first_page_header, full_text)
    currency = "NGN" if ("NGN" in full_text or "₦" in full_text or "NAIRA" in full_text.upper()) else "USD"

    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    expected_debits: Optional[Decimal] = None
    expected_credits: Optional[Decimal] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None

    # Summary table pattern (Access Bank style)
    m_summary = re.search(
        r"Opening Balance\s+Debits\s+Credits\s+Closing Balance[\s\S]*?(\d[\d,.]*\.\d{2})\s+(\d[\d,.]*\.\d{2})\s+(\d[\d,.]*\.\d{2})\s+(\d[\d,.]*\.\d{2})",
        full_text,
        re.IGNORECASE,
    )
    if m_summary:
        opening_balance = clean_decimal(m_summary.group(1))
        expected_debits = clean_decimal(m_summary.group(2))
        expected_credits = clean_decimal(m_summary.group(3))
        closing_balance = clean_decimal(m_summary.group(4))
    else:
        m_op = re.search(r"Opening Balance[:\s]*([₦\$£€■]?\s*[\d,.]+\.\d{2})", full_text, re.IGNORECASE)
        m_cl = re.search(r"Closing Balance[:\s]*([₦\$£€■]?\s*[\d,.]+\.\d{2})", full_text, re.IGNORECASE)
        m_dr = re.search(r"Total Debit[s]?[:\s]*([₦\$£€■]?\s*[\d,.]+\.\d{2})", full_text, re.IGNORECASE)
        m_cr = re.search(r"Total Credit[s]?[:\s]*([₦\$£€■]?\s*[\d,.]+\.\d{2})", full_text, re.IGNORECASE)
        if m_op:
            opening_balance = clean_decimal(m_op.group(1))
        if m_cl:
            closing_balance = clean_decimal(m_cl.group(1))
        if m_dr:
            expected_debits = clean_decimal(m_dr.group(1))
        if m_cr:
            expected_credits = clean_decimal(m_cr.group(1))

    # Statement Period
    m_p1 = re.search(r"Period:\s*(\d{1,2}/\d{1,2}/\d{2,4})\s+TO\s+(\d{1,2}/\d{1,2}/\d{2,4})", full_text, re.IGNORECASE)
    m_p_month = re.search(r"Period:\s*([A-Za-z]+\s+\d+(?:st|nd|rd|th)?,\s+\d{4})\s+TO\s+([A-Za-z]+\s+\d+(?:st|nd|rd|th)?,\s+\d{4})", full_text, re.IGNORECASE)
    m_p_dash = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})\s*[-to]+\s*(\d{1,2}/\d{1,2}/\d{2,4})", full_text, re.IGNORECASE)
    if m_p1:
        period_start, period_end = m_p1.group(1), m_p1.group(2)
    elif m_p_month:
        period_start, period_end = m_p_month.group(1), m_p_month.group(2)
    elif m_p_dash:
        period_start, period_end = m_p_dash.group(1), m_p_dash.group(2)

    date_re = re.compile(r"^\s*(\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}-[A-Za-z]{3}-\d{2,4})\s*(\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}-[A-Za-z]{3}-\d{2,4})?\s*(.*)$")
    amt_pattern = re.compile(r"([,\d.]+\.\d{2})")

    raw_txns: List[Dict[str, Any]] = []
    curr_post: Optional[str] = None
    curr_val: Optional[str] = None
    curr_desc_lines: List[str] = []
    curr_dr = Decimal("0.00")
    curr_cr = Decimal("0.00")
    curr_bal = Decimal("0.00")

    def commit_row():
        nonlocal curr_post, curr_val, curr_desc_lines, curr_dr, curr_cr, curr_bal
        if not curr_post:
            return
        desc = " ".join(curr_desc_lines).strip() or "TRANSACTION"
        if curr_cr > Decimal("0.00"):
            amt = curr_cr
            direction = "credit"
        else:
            amt = curr_dr
            direction = "debit"

        raw_txns.append({
            "date": curr_post,
            "val_date": curr_val or curr_post,
            "description_raw": desc,
            "description_norm": re.sub(r"\s+", " ", desc).strip().lower(),
            "debit": curr_dr,
            "credit": curr_cr,
            "amount": amt,
            "direction": direction,
            "balance": curr_bal,
        })
        curr_post = None
        curr_val = None
        curr_desc_lines = []
        curr_dr = Decimal("0.00")
        curr_cr = Decimal("0.00")
        curr_bal = Decimal("0.00")

    watermarks = [
        r"PLEASE EXAMINE THIS STATEMENT AT ONCE",
        r"CONFIDENTIAL",
        r"OFFICIAL ACCOUNT STATEMENT",
    ]

    for page in reader.pages:
        layout_text = page.extract_text(extraction_mode="layout") or ""
        lines = layout_text.splitlines()

        hdr_idx: Optional[int] = None
        hdr_line: str = ""
        for i, line in enumerate(lines):
            upper = line.upper()
            has_date = any(w in upper for w in ["DATE", "POST", "TRANS DATE"])
            has_money = any(w in upper for w in ["DEBIT", "CREDIT", "WITHDRAWAL", "DEPOSIT", "PAY IN", "PAY OUT", "DR", "CR"])
            has_bal = any(w in upper for w in ["BALANCE", "BAL"])
            if has_date and has_money and has_bal:
                hdr_idx = i
                hdr_line = line
                break

        if hdr_idx is None:
            continue

        upper_hdr = hdr_line.upper()
        pos_dr = -1.0
        for kw in ["DEBITS", "DEBIT", "WITHDRAWALS", "WITHDRAWAL", "PAY OUT", "OUTFLOWS", "DR"]:
            p = upper_hdr.find(kw)
            if p != -1:
                pos_dr = p + len(kw) / 2.0
                break

        pos_cr = -1.0
        for kw in ["CREDITS", "CREDIT", "DEPOSITS", "DEPOSIT", "PAY IN", "INFLOWS", "CR"]:
            p = upper_hdr.find(kw)
            if p != -1:
                pos_cr = p + len(kw) / 2.0
                break

        pos_bal = -1.0
        for kw in ["BALANCE", "BAL"]:
            p = upper_hdr.find(kw)
            if p != -1:
                pos_bal = p + len(kw) / 2.0
                break

        if pos_dr == -1.0 or pos_cr == -1.0 or pos_bal == -1.0:
            continue

        col_dr_start = min(pos_dr - 12, pos_cr - 12)

        for line in lines[hdr_idx + 1:]:
            if not line.strip():
                continue
            m = date_re.match(line)
            if not m and any(f in line for f in ["Failing receipt", "All correspondence", "Branch Manager", "You must advise", "TOTAL"]):
                break

            if m:
                commit_row()
                curr_post = m.group(1)
                curr_val = m.group(2)

                matches = list(amt_pattern.finditer(line))
                first_amt_pos = len(line)
                for am in matches:
                    start, end = am.span()
                    val = clean_decimal(am.group(1))
                    amt_center = (start + end) / 2.0
                    d_dr = abs(amt_center - pos_dr)
                    d_cr = abs(amt_center - pos_cr)
                    d_bal = abs(amt_center - pos_bal)
                    min_d = min(d_dr, d_cr, d_bal)
                    if min_d == d_dr:
                        curr_dr = val
                    elif min_d == d_cr:
                        curr_cr = val
                    else:
                        curr_bal = val
                    first_amt_pos = min(first_amt_pos, start)

                desc_start = m.end(2) if m.group(2) else m.end(1)
                raw_desc = line[desc_start:first_amt_pos]
                for wm in watermarks:
                    raw_desc = re.sub(wm, "", raw_desc, flags=re.IGNORECASE)
                clean_desc = raw_desc.strip()
                if clean_desc:
                    curr_desc_lines.append(clean_desc)
            elif curr_post:
                raw_desc = line[: int(col_dr_start)]
                for wm in watermarks:
                    raw_desc = re.sub(wm, "", raw_desc, flags=re.IGNORECASE)
                clean_desc = raw_desc.strip()
                if clean_desc:
                    curr_desc_lines.append(clean_desc)

    commit_row()

    if not raw_txns:
        return None

    calc_total_debits = sum(t["debit"] for t in raw_txns)
    calc_total_credits = sum(t["credit"] for t in raw_txns)

    first_bal = raw_txns[0]["balance"]
    last_bal = raw_txns[-1]["balance"]

    if opening_balance is None and first_bal != Decimal("0.00"):
        opening_balance = first_bal + raw_txns[0]["debit"] - raw_txns[0]["credit"]
    if closing_balance is None and last_bal != Decimal("0.00"):
        closing_balance = last_bal

    if opening_balance is None:
        opening_balance = Decimal("0.00")
    if closing_balance is None:
        closing_balance = Decimal("0.00")

    running_calc = opening_balance + calc_total_credits - calc_total_debits

    math_ok = True
    math_error_detail = None

    diff_close = abs(running_calc - closing_balance)
    diff_last = abs(running_calc - last_bal)

    # Arithmetic check: matches statement closing balance OR matches last row's balance (for statement excerpts)
    if diff_close > Decimal("5.00") and diff_last > Decimal("5.00"):
        math_ok = False
        math_error_detail = (
            f"Closing balance mismatch: opening (₦{opening_balance:,.2f}) + credits (₦{calc_total_credits:,.2f}) "
            f"- debits (₦{calc_total_debits:,.2f}) = ₦{running_calc:,.2f}, but statement specifies ₦{closing_balance:,.2f} "
            f"(last row balance was ₦{last_bal:,.2f})."
        )
    elif expected_debits and expected_debits == calc_total_debits and expected_credits and expected_credits != calc_total_credits:
        math_ok = False
        math_error_detail = f"Credits total mismatch: parsed ₦{calc_total_credits:,.2f}, statement says ₦{expected_credits:,.2f}."

    processed = []
    for txn in raw_txns:
        fp = generate_fingerprint(
            date_str=txn["date"],
            amount=float(txn["amount"]),
            direction=txn["direction"],
            desc_norm=txn["description_norm"],
            balance=float(txn["balance"]) if txn["balance"] != Decimal("0.00") else None,
        )
        processed.append({
            "date": txn["date"],
            "value_date": txn.get("val_date", txn["date"]),
            "description_raw": txn["description_raw"],
            "description_norm": txn["description_norm"],
            "amount": float(txn["amount"]),
            "direction": txn["direction"],
            "balance": float(txn["balance"]) if txn["balance"] != Decimal("0.00") else None,
            "fingerprint": fp,
            "element": "needs_review",
            "tier": "ingestion",
            "confidence": 0.0,
            "reason": f"Parsed from {bank_name} statement",
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
        "total_credits": float(calc_total_credits),
        "total_debits": float(calc_total_debits),
        "math_ok": math_ok,
        "math_error_detail": math_error_detail,
        "transaction_count": len(processed),
        "transactions": processed,
    }


def _parse_standard_statement(
    reader: pypdf.PdfReader,
    full_text: str,
    all_lines: List[str],
    filename: str,
) -> Dict[str, Any]:
    """
    Fallback parser for standard line-by-line digital bank statements and ReportLab generated test fixtures.
    """
    first_page_header = (reader.pages[0].extract_text() or "")[:800]
    bank_name = _detect_bank_name(first_page_header, full_text)
    currency = "NGN" if ("NGN" in full_text or "₦" in full_text or "NAIRA" in full_text.upper()) else "USD"

    period_start = None
    period_end = None
    p_m = re.search(r"(\d{2}/\d{2}/\d{4})\s*[-to]+\s*(\d{2}/\d{2}/\d{4})", full_text, re.IGNORECASE)
    if p_m:
        period_start, period_end = p_m.group(1), p_m.group(2)
    else:
        p_dash = re.search(r"(\d{4}-\d{2}-\d{2})\s*[-to]+\s*(\d{4}-\d{2}-\d{2})", full_text, re.IGNORECASE)
        if p_dash:
            period_start, period_end = p_dash.group(1), p_dash.group(2)

    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    total_credits: Optional[Decimal] = None
    total_debits: Optional[Decimal] = None

    for i, line in enumerate(all_lines[:60]):
        if "Account No" in line and i + 13 < len(all_lines):
            if "Debits" in all_lines[i + 4] and "Credits" in all_lines[i + 5]:
                opening_balance = clean_decimal(all_lines[i + 10])
                total_debits = clean_decimal(all_lines[i + 11])
                total_credits = clean_decimal(all_lines[i + 12])
                closing_balance = clean_decimal(all_lines[i + 13])
                break

    if opening_balance is None:
        for line in all_lines[:40]:
            if "Opening Balance" in line:
                m = re.search(r"Opening Balance[:\s]*([₦\$£€]?\s*[\d,.]+\.\d{2})", line, re.IGNORECASE)
                if m:
                    opening_balance = clean_decimal(m.group(1))
            if "Closing Balance" in line:
                m = re.search(r"Closing Balance[:\s]*([₦\$£€]?\s*[\d,.]+\.\d{2})", line, re.IGNORECASE)
                if m:
                    closing_balance = clean_decimal(m.group(1))

    date_regex = re.compile(r"^(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2}|\d{2}-[A-Za-z]{3}-\d{4})$")
    amount_regex = re.compile(r"^[₦\$£€]?\s*[\d,.]+\.\d{2}$|^-$")
    table_headers = {
        "post date", "value date", "date", "narration", "description", "ref/cheque no.",
        "debits", "credits", "balance", "debit ($)", "credit ($)", "balance ($)",
        "withdrawal", "deposit", "withdrawals (debit)", "deposits (credit)", "pay in", "pay out"
    }

    raw_transactions: List[Dict[str, Any]] = []
    idx = 0
    num_lines = len(all_lines)

    while idx < num_lines:
        line = all_lines[idx]

        if line.lower() in table_headers:
            idx += 1
            continue

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
                if date_regex.match(curr) and idx + 1 < num_lines and date_regex.match(all_lines[idx + 1]):
                    break
                tokens.append(curr)
                idx += 1
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

    if not raw_transactions:
        raise ValueError(
            "No transactions could be parsed from this PDF statement. "
            "Please ensure it contains a recognizable transaction table with dates, descriptions, and amounts."
        )

    first_txn = raw_transactions[0]
    last_txn = raw_transactions[-1]

    if opening_balance is None and first_txn["balance"] != Decimal("0.00"):
        opening_balance = first_txn["balance"] + first_txn["debit"] - first_txn["credit"]

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
            ref=txn.get("ref"),
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
            "reason": f"Parsed from {bank_name} statement",
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


def parse_pdf_statement(file_input: Union[str, bytes, BinaryIO], filename: str = "statement.pdf") -> Dict[str, Any]:
    """
    Parses digital text-based Nigerian and generic bank statement PDFs (Zenith, Access, GTBank, Fidelity, PalmPay, etc.).
    Extracts header metadata (Bank Name, Period, Opening/Closing Balances),
    all transaction line items, and performs complete arithmetic verification.
    """
    if isinstance(file_input, str):
        with open(file_input, "rb") as f:
            pdf_bytes = f.read()
    elif isinstance(file_input, bytes):
        pdf_bytes = file_input
    else:
        pdf_bytes = file_input.read()

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))

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

    # 1. PalmPay Statement Handler (Digital Fintech format with timestamps and signed amounts)
    if (
        re.search(r"\bpalmpay\b", full_text, re.IGNORECASE)
        or ("Total Money In" in full_text and "Transaction Date Transaction Detail" in full_text)
        or "Money In (NGN)" in full_text
    ):
        return _parse_palmpay_pdf(reader, filename=filename)

    # 2. Universal Tabular Layout Parser (works across Zenith, Access, GTBank, Fidelity, etc.)
    tabular_result = _parse_tabular_layout_pdf(reader, filename=filename)
    if tabular_result and tabular_result.get("transaction_count", 0) > 0:
        return tabular_result

    # 3. Standard line-by-line fallback (for test fixtures and single-column text statements)
    return _parse_standard_statement(reader, full_text=full_text, all_lines=all_lines, filename=filename)
