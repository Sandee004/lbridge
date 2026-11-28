import os
from decimal import Decimal
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

def generate_demo_excel(filename="demo_statement.xlsx"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Account Statement"

    # Header styling
    brand_font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    brand_fill = PatternFill(start_color="C2410C", end_color="C2410C", fill_type="solid") # Deep Orange
    tbl_hdr_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    tbl_hdr_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid") # Navy Slate

    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    # Title block
    ws.merge_cells("A1:G1")
    ws["A1"] = "ACCESS BANK PLC - CORPORATE ACCOUNT STATEMENT"
    ws["A1"].font = brand_font
    ws["A1"].fill = brand_fill
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30

    # Metadata block
    ws["A3"] = "Account Name:"
    ws["B3"] = "ADEFEMI LOGISTICS & CONSULTING LTD"
    ws["A4"] = "Account Number:"
    ws["B4"] = "1420088921"
    ws["A5"] = "Currency:"
    ws["B5"] = "NGN"

    ws["D3"] = "Statement Period:"
    ws["E3"] = "01/10/2026 - 31/10/2026"
    ws["D4"] = "Opening Balance:"
    ws["E4"] = 154250.00
    ws["D5"] = "Branch:"
    ws["E5"] = "Victoria Island Commercial Hub"

    for r in range(3, 6):
        ws[f"A{r}"].font = Font(bold=True, size=9)
        ws[f"D{r}"].font = Font(bold=True, size=9)
        ws[f"B{r}"].font = Font(size=9)
        ws[f"E{r}"].font = Font(size=9)
    ws["E4"].number_format = "#,##0.00"

    # Table headers at Row 7
    headers = ["Transaction Date", "Value Date", "Narration", "Reference Number", "Debit", "Credit", "Balance"]
    ws.row_dimensions[7].height = 22
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=7, column=col_idx, value=h)
        cell.font = tbl_hdr_font
        cell.fill = tbl_hdr_fill
        cell.alignment = Alignment(horizontal="center" if "Date" in h else ("right" if h in ["Debit", "Credit", "Balance"] else "left"), vertical="center")

    txns_data = [
        ("01/10/2026", "01/10/2026", "R-1523348849/NYSC STATE:OVERHEADPAYMENT:CBN", "REMITA-9015233", Decimal("0.00"), Decimal("65000.00")),
        ("01/10/2026", "01/10/2026", "MOBILE TRF TO PPL /AMAKA JANE OKORO", "TRF-0010492", Decimal("25000.00"), Decimal("0.00")),
        ("01/10/2026", "01/10/2026", "COMMISSION MOBILE TRF TO PPL /AMAKA JANE OKORO", "COMM-0010492", Decimal("25.00"), Decimal("0.00")),
        ("01/10/2026", "01/10/2026", "VAT MOBILE TRF TO PPL /AMAKA JANE OKORO", "VAT-0010492", Decimal("1.88"), Decimal("0.00")),
        ("02/10/2026", "02/10/2026", "SPECTRANET 4G LTE BROADBAND RENEWAL 50GB", "SPEC-9940129", Decimal("18500.00"), Decimal("0.00")),
        ("02/10/2026", "02/10/2026", "TRF/FRM/0029103994/REF88219", "TRF-88219", Decimal("0.00"), Decimal("50000.00")),
        ("03/10/2026", "03/10/2026", "IKEDC PREPAID TOKEN 042918201948 - IKEJA ELECTRIC", "IKEDC-109384", Decimal("25000.00"), Decimal("0.00")),
        ("03/10/2026", "03/10/2026", "POS 4910283 WTH TRF", "POS-4910283", Decimal("18500.00"), Decimal("0.00")),
        ("04/10/2026", "04/10/2026", "POS SETTLEMENT/PAYSTACK/2026-10-04/SETTLEMENT", "PSTK-4892019", Decimal("0.00"), Decimal("485000.00")),
        ("04/10/2026", "04/10/2026", "MTN DATA CORPORATE FIBER BROADBAND VGC", "MTN-9910482", Decimal("45000.00"), Decimal("0.00")),
        ("05/10/2026", "05/10/2026", "AIRTEL DATA TOPUP 08023456789 BUNDLE", "AIRT-4829104", Decimal("5000.00"), Decimal("0.00")),
        ("05/10/2026", "05/10/2026", "ATM WDL 0482910 ACCESS BANK LEKKI BR", "ATM-4829104", Decimal("20000.00"), Decimal("0.00")),
        ("06/10/2026", "06/10/2026", "BOVAS & COMPANY LTD FUEL LEKKI EXP", "POS-7749102", Decimal("22000.00"), Decimal("0.00")),
        ("07/10/2026", "07/10/2026", "STARLINK INTERNET RESIDENTIAL LAGOS NIGERIA", "STLNK-883921", Decimal("38000.00"), Decimal("0.00")),
        ("08/10/2026", "08/10/2026", "TRANSFER FROM DIRECTOR: FEMI ADEBAYO INJECTION", "DIR-EQ-10492", Decimal("0.00"), Decimal("1500000.00")),
        ("08/10/2026", "08/10/2026", "SMS Alert Fee-29/09-28/10/2026 + VAT", "SMS-9894604", Decimal("5.38"), Decimal("0.00")),
        ("08/10/2026", "08/10/2026", "TOTALENERGIES FILLING STATION VICTORIA ISLAND", "POS-9910429", Decimal("28500.00"), Decimal("0.00")),
        ("09/10/2026", "09/10/2026", "SLOT SYSTEMS COMPUTER VILLAGE IKEJA - HP LAPTOP", "POS-9910482", Decimal("780000.00"), Decimal("0.00")),
        ("10/10/2026", "10/10/2026", "FLUTTERWAVE PAYOUT NGN 10/10/2026 CLIENT FEES", "FLW-10492810", Decimal("0.00"), Decimal("320000.00")),
        ("11/10/2026", "11/10/2026", "BUYPOWER.NG ELECTRICITY TOKEN EKEDC ISLAND", "BP-991048201", Decimal("35000.00"), Decimal("0.00")),
        ("12/10/2026", "12/10/2026", "SHOPRITE ADENIRAN OGUNSANYA SURULERE", "POS-4482910", Decimal("42300.00"), Decimal("0.00")),
        ("13/10/2026", "13/10/2026", "NIP/ZENITH/DANGOTE SUGAR RETAINER PYMT", "ZEN-4820194", Decimal("0.00"), Decimal("1200000.00")),
        ("14/10/2026", "14/10/2026", "BOLT RIDE LEKKI TO MARINA LAGOS", "BLT-8829104", Decimal("4800.00"), Decimal("0.00")),
        ("15/10/2026", "15/10/2026", "MOBILE TRF TO PPL /CHINEDU OKAFOR", "TRF-CHINEDU", Decimal("75000.00"), Decimal("0.00")),
        ("16/10/2026", "16/10/2026", "THE PLACE RESTAURANT LEKKI PHASE 1 FOOD", "POS-1194029", Decimal("11500.00"), Decimal("0.00")),
        ("17/10/2026", "17/10/2026", "FGN Stamp Duty for 1 txns 11/10 - 17/10/26", "STAMP-20261", Decimal("50.00"), Decimal("0.00")),
        ("18/10/2026", "18/10/2026", "NNPC RETAIL STATION OBA AKRAN IKEJA FUEL", "POS-8839201", Decimal("30000.00"), Decimal("0.00")),
        ("19/10/2026", "19/10/2026", "NIP/STANBIC/EMMANUEL O./PERSONAL", "STB-0019284", Decimal("40000.00"), Decimal("0.00")),
        ("20/10/2026", "20/10/2026", "GIG LOGISTICS INTERSTATE DISPATCH ABUJA", "GIGL-001948", Decimal("14500.00"), Decimal("0.00")),
        ("21/10/2026", "21/10/2026", "MEGA CHICKEN IKOTA RESTAURANT LUNCH", "POS-3392018", Decimal("8900.00"), Decimal("0.00")),
        ("22/10/2026", "22/10/2026", "NIP/GTB/CHUKWUDI ENTERPRISES/OCT INVOICE 042", "GTB-9910482", Decimal("0.00"), Decimal("750000.00")),
        ("25/10/2026", "25/10/2026", "INWARD NIP: KUDA/IBRAHIM BELLO/CONSULTING FEE", "KUD-1092847", Decimal("0.00"), Decimal("180000.00")),
        ("27/10/2026", "27/10/2026", "DIRECT DEP MONIEPOINT/SETTLEMENT W42 POS", "MNPT-883920", Decimal("0.00"), Decimal("195500.00")),
        ("28/10/2026", "28/10/2026", "DIRECTOR WITHDRAWAL / PERSONAL DRAWING OCT", "DIR-WDL-991", Decimal("300000.00"), Decimal("0.00")),
        ("30/10/2026", "30/10/2026", "MONTHLY ACCOUNT MAINTENANCE FEE ACC", "CHG-OCT-202", Decimal("1500.00"), Decimal("0.00"))
    ]

    running_bal = Decimal("154250.00")
    start_row = 8
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

    for idx, (dt, val_dt, narr, ref, deb, cr) in enumerate(txns_data):
        row_num = start_row + idx
        running_bal = running_bal - deb + cr

        ws.cell(row=row_num, column=1, value=dt).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=2, value=val_dt).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=3, value=narr).alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=4, value=ref).alignment = Alignment(horizontal="left")

        c_deb = ws.cell(row=row_num, column=5, value=float(deb) if deb > 0 else "")
        c_deb.number_format = "#,##0.00"
        c_deb.font = Font(color="DC2626" if deb > 0 else "000000") # Red debits
        c_deb.alignment = Alignment(horizontal="right")

        c_cr = ws.cell(row=row_num, column=6, value=float(cr) if cr > 0 else "")
        c_cr.number_format = "#,##0.00"
        c_cr.font = Font(color="16A34A" if cr > 0 else "000000") # Green credits
        c_cr.alignment = Alignment(horizontal="right")

        c_bal = ws.cell(row=row_num, column=7, value=float(running_bal))
        c_bal.number_format = "#,##0.00"
        c_bal.alignment = Alignment(horizontal="right")

        for col_i in range(1, 8):
            cell = ws.cell(row=row_num, column=col_i)
            cell.border = thin_border
            if idx % 2 == 1:
                cell.fill = zebra_fill

    # Set column widths
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 46
    ws.column_dimensions["D"].width = 20
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 18
    ws.column_dimensions["G"].width = 20

    wb.save(filename)
    print(f"Generated {filename} successfully with {len(txns_data)} transactions.")
    print(f"Opening: 154,250.00, Closing: {running_bal:,.2f}")

if __name__ == "__main__":
    generate_demo_excel()
