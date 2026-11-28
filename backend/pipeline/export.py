import csv
import io
from typing import List
import openpyxl
from models import Transaction


def sanitize_text_cell(val: any) -> str:
    """
    P4.3: Prefix any cell starting with '=', '+', '-', '@' (after trimming)
    with a single quote, in every text column, to neutralize CSV formula injection.
    """
    if val is None:
        return ""
    s = str(val)
    stripped = s.strip()
    if stripped and stripped[0] in ("=", "+", "-", "@"):
        return "'" + s
    return s


def normalize_category_display(elem: str | None) -> str:
    if not elem:
        return "Needs Review"
    mapping = {
        "asset": "Assets",
        "liability": "Liabilities",
        "income": "Income",
        "expense": "Expenses",
        "capital": "Capital",
        "cogs": "Cost of Goods Sold",
        "transfer": "Internal Transfer",
        "taxes": "Taxes & VAT",
        "needs_review": "Needs Review",
    }
    return mapping.get(elem.lower(), elem.title())


def export_flat_csv(transactions: List[Transaction]) -> str:
    """Export transactions to a flat CSV register with formula injection guards."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow([
        "ID",
        "Date",
        "Value_Date",
        "Narration",
        "Direction",
        "Amount",
        "Element",
        "Tier",
        "Confidence",
        "Status",
    ])
    for t in transactions:
        writer.writerow([
            sanitize_text_cell(t.id),
            sanitize_text_cell(t.date),
            sanitize_text_cell(t.value_date or t.date),
            sanitize_text_cell(t.description_raw),
            sanitize_text_cell(t.direction),
            round(float(t.amount), 2),
            sanitize_text_cell(normalize_category_display(t.element)),
            sanitize_text_cell(t.tier or "auto"),
            round(float(t.confidence if t.confidence is not None else 1.0), 2),
            sanitize_text_cell(t.status or "auto"),
        ])
    return output.getvalue()


def export_journal_csv(transactions: List[Transaction]) -> str:
    """
    Export transactions as a balanced double-entry journal CSV.
    P4.2: Refuses if any transactions are unresolved (needs_review).
    """
    unresolved = [t for t in transactions if (t.element or "").lower() == "needs_review"]
    if unresolved:
        raise ValueError(
            f"Cannot export journal: {len(unresolved)} unresolved transaction(s) require review before closing the ledger."
        )

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["Journal_Date", "Journal_Number", "Account_Name", "Debit", "Credit", "Description"])

    for t in transactions:
        clean_desc = sanitize_text_cell(t.description_raw)
        elem = sanitize_text_cell(normalize_category_display(t.element))
        jrn_id = sanitize_text_cell(f"JRN-{t.id[:8].upper()}")
        date_str = sanitize_text_cell(t.date)
        amt = round(float(t.amount), 2)

        if t.direction == "credit":
            # Bank Account Debited (money received), Category Credited
            writer.writerow([date_str, jrn_id, "Bank Account", amt, 0.0, clean_desc])
            writer.writerow([date_str, jrn_id, elem, 0.0, amt, clean_desc])
        else:
            # Category Debited (money spent), Bank Account Credited
            writer.writerow([date_str, jrn_id, elem, amt, 0.0, clean_desc])
            writer.writerow([date_str, jrn_id, "Bank Account", 0.0, amt, clean_desc])

    return output.getvalue()


def export_excel_workbook(transactions: List[Transaction]) -> bytes:
    """
    P4.4: XLSX export with three sheets:
    - Categorized Rows
    - 5-Element Summary (with SUMIFS formulas referencing Categorized Rows)
    - Audit Log (provenance, tier, rule/model, confidence, status)
    """
    wb = openpyxl.Workbook()

    # Sheet 1: Categorized Rows
    ws_rows = wb.active
    ws_rows.title = "Categorized Rows"

    headers_rows = [
        "Transaction ID",
        "Date",
        "Value Date",
        "Description",
        "Direction",
        "Amount",
        "Category",
        "Tier",
        "Confidence",
        "Status",
    ]
    ws_rows.append(headers_rows)
    for t in transactions:
        ws_rows.append([
            t.id,
            t.date,
            t.value_date or t.date,
            t.description_raw,
            t.direction,
            round(float(t.amount), 2),
            normalize_category_display(t.element),
            t.tier or "auto",
            round(float(t.confidence if t.confidence is not None else 1.0), 2),
            t.status or "auto",
        ])

    # Sheet 2: 5-Element Summary
    ws_summary = wb.create_sheet(title="5-Element Summary")
    ws_summary.append(["Element", "Total Amount"])

    core_elements = [
        "Assets",
        "Liabilities",
        "Income",
        "Expenses",
        "Capital",
        "Cost of Goods Sold",
        "Internal Transfer",
        "Taxes & VAT",
        "Needs Review",
    ]
    for idx, elem in enumerate(core_elements, start=2):
        # Column F is Amount, Column G is Category in 'Categorized Rows'
        formula = f"=SUMIFS('Categorized Rows'!$F:$F, 'Categorized Rows'!$G:$G, A{idx})"
        ws_summary.append([elem, formula])

    total_row_idx = len(core_elements) + 2
    ws_summary.append(["Total", f"=SUM(B2:B{total_row_idx - 1})"])

    # Sheet 3: Audit Log
    ws_audit = wb.create_sheet(title="Audit Log")
    headers_audit = [
        "Transaction ID",
        "Date",
        "Description",
        "Amount",
        "Element",
        "Tier",
        "Rule ID / Model",
        "Confidence",
        "Status",
        "Reason",
    ]
    ws_audit.append(headers_audit)
    for t in transactions:
        ws_audit.append([
            t.id,
            t.date,
            t.description_raw,
            round(float(t.amount), 2),
            normalize_category_display(t.element),
            t.tier or "auto",
            str(t.rule_id) if t.rule_id else (t.tier or "llm"),
            round(float(t.confidence if t.confidence is not None else 1.0), 2),
            t.status or "auto",
            t.reason or "",
        ])

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
