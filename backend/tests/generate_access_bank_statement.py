import os
from decimal import Decimal
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class AccessNumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(AccessNumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont('Helvetica', 6.5)
        self.setFillColor(colors.HexColor('#6b7280'))
        footer_text = "This report indicates transaction details on your account(s) for the requested period. Access Bank Plc • contactcenter@accessbankplc.com • 01-2712005-7"
        self.drawString(26, 18, footer_text)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 26, 18, page_str)
        self.restoreState()


def generate_access_statement(output_filename="access_bank_statement.pdf"):
    # Ordered chronologically, keeping running balance always positive and realistic
    raw_txns = [
        ('01/10/2026', '01/10/2026', 'R-1523348849/NYSC STATE:OVERHEADPAYMENT:CBN:1523360268-1523', 'REMITA-9015233488490', Decimal('0.00'), Decimal('65000.00')),
        ('01/10/2026', '01/10/2026', 'MOBILE TRF TO PPL /SANDRA TOMSIN OYAREKHUA', '000014261001042704216809676052', Decimal('25000.00'), Decimal('0.00')),
        ('01/10/2026', '01/10/2026', 'COMMISSION MOBILE TRF TO PPL /SANDRA TOMSIN OYAREKHUA', '000014261001042704216809676052', Decimal('25.00'), Decimal('0.00')),
        ('01/10/2026', '01/10/2026', 'VAT MOBILE TRF TO PPL /SANDRA TOMSIN OYAREKHUA', '000014261001042704216809676052', Decimal('1.88'), Decimal('0.00')),
        ('02/10/2026', '02/10/2026', 'SPECTRANET 4G LTE BROADBAND RENEWAL 50GB', 'SPEC-9940129', Decimal('18500.00'), Decimal('0.00')),
        ('02/10/2026', '02/10/2026', 'TRF/FRM/0029103994/REF88219', 'TRF-88219', Decimal('0.00'), Decimal('50000.00')),
        ('03/10/2026', '03/10/2026', 'IKEDC PREPAID TOKEN 042918201948 - IKEJA ELECTRIC', 'IKEDC-109384', Decimal('25000.00'), Decimal('0.00')),
        ('03/10/2026', '03/10/2026', 'POS 4910283 WTH TRF', 'POS-4910283', Decimal('18500.00'), Decimal('0.00')),
        ('04/10/2026', '04/10/2026', 'POS SETTLEMENT/PAYSTACK/2026-10-04/SETTLEMENT-8821', 'PSTK-489201948', Decimal('0.00'), Decimal('485000.00')),
        ('04/10/2026', '04/10/2026', 'MTN DATA CORPORATE FIBER BROADBAND VGC', '000014261019283', Decimal('45000.00'), Decimal('0.00')),
        ('05/10/2026', '05/10/2026', 'AIRTEL DATA TOPUP 08023456789 BUNDLE', 'AIRT-4829104', Decimal('5000.00'), Decimal('0.00')),
        ('05/10/2026', '05/10/2026', 'ATM WDL 0482910 ACCESS BANK LEKKI BR', 'ATM-4829104', Decimal('20000.00'), Decimal('0.00')),
        ('06/10/2026', '06/10/2026', 'BOVAS & COMPANY LTD FUEL LEKKI EXP', 'POS-7749102', Decimal('22000.00'), Decimal('0.00')),
        ('06/10/2026', '06/10/2026', 'NFT/B/O/VERITAS RE/ZENITH BANK DIV/ZENITH BANK INTERIM DIV 2', '07774789', Decimal('0.00'), Decimal('4765.50')),
        ('07/10/2026', '07/10/2026', 'STARLINK INTERNET RESIDENTIAL LAGOS NIGERIA', 'STLNK-883921', Decimal('38000.00'), Decimal('0.00')),
        ('07/10/2026', '07/10/2026', 'MOBILE TRF TO PPL /SOFIAT OMOTOLA OKEDEJ', '0000142610141056022244261106032', Decimal('35000.00'), Decimal('0.00')),
        ('07/10/2026', '07/10/2026', 'COMMISSION MOBILE TRF TO PPL /SOFIAT OMOTOLA OKEDEJ', '0000142610141056022244261106032', Decimal('25.00'), Decimal('0.00')),
        ('07/10/2026', '07/10/2026', 'VAT MOBILE TRF TO PPL /SOFIAT OMOTOLA OKEDEJ', '0000142610141056022244261106032', Decimal('1.88'), Decimal('0.00')),
        ('08/10/2026', '08/10/2026', 'TRANSFER FROM DIRECTOR: FEMI ADEBAYO INJECTION', 'DIR-EQ-10492', Decimal('0.00'), Decimal('1500000.00')),
        ('08/10/2026', '08/10/2026', 'SMS Alert Fee-29/09-28/10/2026 + VAT', '989460442', Decimal('5.38'), Decimal('0.00')),
        ('08/10/2026', '08/10/2026', 'TOTALENERGIES FILLING STATION VICTORIA ISLAND', 'POS-9910429', Decimal('28500.00'), Decimal('0.00')),
        ('09/10/2026', '09/10/2026', 'SLOT SYSTEMS COMPUTER VILLAGE IKEJA - HP LAPTOP', 'POS-9910482', Decimal('780000.00'), Decimal('0.00')),
        ('10/10/2026', '10/10/2026', 'FLUTTERWAVE PAYOUT NGN 10/10/2026 CLIENT FEES', 'FLW-10492810', Decimal('0.00'), Decimal('320000.00')),
        ('10/10/2026', '10/10/2026', 'UBER NIGERIA TRIP LAGOS ISLAND 12/10', 'UBR-9940192', Decimal('6450.00'), Decimal('0.00')),
        ('11/10/2026', '11/10/2026', 'BUYPOWER.NG ELECTRICITY TOKEN EKEDC ISLAND', 'BP-991048201', Decimal('35000.00'), Decimal('0.00')),
        ('11/10/2026', '11/10/2026', 'MISC PYMT 9910482', 'MSC-9910482', Decimal('15000.00'), Decimal('0.00')),
        ('12/10/2026', '12/10/2026', 'SHOPRITE ADENIRAN OGUNSANYA SURULERE', 'POS-4482910', Decimal('42300.00'), Decimal('0.00')),
        ('12/10/2026', '12/10/2026', 'BILL PMT 109384729', 'BPM-109384729', Decimal('22000.00'), Decimal('0.00')),
        ('13/10/2026', '13/10/2026', 'NIP/ZENITH/DANGOTE SUGAR RETAINER PYMT', 'ZEN-482019482', Decimal('0.00'), Decimal('1200000.00')),
        ('14/10/2026', '14/10/2026', 'BOLT RIDE LEKKI TO MARINA LAGOS', 'BLT-8829104', Decimal('4800.00'), Decimal('0.00')),
        ('14/10/2026', '14/10/2026', 'TRANSFER TO 994019201', 'TRF-994019201', Decimal('35000.00'), Decimal('0.00')),
        ('15/10/2026', '15/10/2026', 'MOBILE TRF TO PPL /CHINEDU OKAFOR', '000014261015151633238596237518', Decimal('75000.00'), Decimal('0.00')),
        ('15/10/2026', '15/10/2026', 'COMMISSION MOBILE TRF TO PPL /CHINEDU OKAFOR', '000014261015151633238596237518', Decimal('50.00'), Decimal('0.00')),
        ('15/10/2026', '15/10/2026', 'VAT MOBILE TRF TO PPL /CHINEDU OKAFOR', '000014261015151633238596237518', Decimal('3.75'), Decimal('0.00')),
        ('16/10/2026', '16/10/2026', 'THE PLACE RESTAURANT LEKKI PHASE 1 FOOD', 'POS-1194029', Decimal('11500.00'), Decimal('0.00')),
        ('16/10/2026', '16/10/2026', 'SMILE COMMUNICATIONS RECHARGE ROUTER 0702', 'SMILE-991048', Decimal('15000.00'), Decimal('0.00')),
        ('17/10/2026', '17/10/2026', 'FGN Stamp Duty for 1 txns 11/10 - 17/10/26', 'STAMP-202610', Decimal('50.00'), Decimal('0.00')),
        ('17/10/2026', '17/10/2026', 'NFT/B/O/NIBSS/PYT 68/MTN-NIG-DIVIDEND', '57547180', Decimal('0.00'), Decimal('12450.00')),
        ('18/10/2026', '18/10/2026', 'NNPC RETAIL STATION OBA AKRAN IKEJA FUEL', 'POS-8839201', Decimal('30000.00'), Decimal('0.00')),
        ('18/10/2026', '18/10/2026', 'SETTLEMENT 90184-B', 'SET-90184B', Decimal('0.00'), Decimal('85000.00')),
        ('19/10/2026', '19/10/2026', 'PUNCH OFFICE FURNITURE PALMGROVE LAGOS DESKS', 'NIP-4820194', Decimal('350000.00'), Decimal('0.00')),
        ('19/10/2026', '19/10/2026', 'NIP/STANBIC/EMMANUEL O./PERSONAL', 'STB-0019284', Decimal('40000.00'), Decimal('0.00')),
        ('20/10/2026', '20/10/2026', 'GIG LOGISTICS INTERSTATE DISPATCH ABUJA', 'GIGL-001948', Decimal('14500.00'), Decimal('0.00')),
        ('21/10/2026', '21/10/2026', 'MEGA CHICKEN IKOTA RESTAURANT LUNCH', 'POS-3392018', Decimal('8900.00'), Decimal('0.00')),
        ('22/10/2026', '22/10/2026', 'NIP/GTB/CHUKWUDI ENTERPRISES/OCT INVOICE 042', 'GTB-991048201', Decimal('0.00'), Decimal('750000.00')),
        ('23/10/2026', '23/10/2026', 'IBEDC PREPAID METER RECHARGE IBADAN BR', 'IBEDC-882194', Decimal('12000.00'), Decimal('0.00')),
        ('24/10/2026', '24/10/2026', 'CHOPPIES SUPERMARKET IKEJA CITY MALL', 'POS-5591029', Decimal('19250.00'), Decimal('0.00')),
        ('25/10/2026', '25/10/2026', 'INWARD NIP: KUDA/IBRAHIM BELLO/CONSULTING FEE', 'KUD-10928471', Decimal('0.00'), Decimal('180000.00')),
        ('26/10/2026', '26/10/2026', 'JUST RITE SUPERMARKET ISOLO STORE', 'POS-6629104', Decimal('16400.00'), Decimal('0.00')),
        ('27/10/2026', '27/10/2026', 'DIRECT DEP MONIEPOINT/SETTLEMENT W42 POS', 'MNPT-8839201', Decimal('0.00'), Decimal('195500.00')),
        ('28/10/2026', '28/10/2026', 'DIRECTOR WITHDRAWAL / PERSONAL DRAWING OCT', 'DIR-WDL-99102', Decimal('300000.00'), Decimal('0.00')),
        ('29/10/2026', '29/10/2026', 'SMS Alert Fee-29/09-28/10/2026 + VAT', '989460599', Decimal('5.38'), Decimal('0.00')),
        ('30/10/2026', '30/10/2026', 'MONTHLY ACCOUNT MAINTENANCE FEE ACC', 'CHG-OCT-2026', Decimal('1500.00'), Decimal('0.00')),
        ('31/10/2026', '31/10/2026', 'MOBILE TRF TO PPL /SANDRA TOMSIN OYAREKHUA', '000014261031083821274892285361', Decimal('450.00'), Decimal('0.00')),
        ('31/10/2026', '31/10/2026', 'COMMISSION MOBILE TRF TO PPL /SANDRA TOMSIN OYAREKHUA', '000014261031083821274892285361', Decimal('10.00'), Decimal('0.00')),
        ('31/10/2026', '31/10/2026', 'VAT MOBILE TRF TO PPL /SANDRA TOMSIN OYAREKHUA', '000014261031083821274892285361', Decimal('0.75'), Decimal('0.00')),
    ]

    opening_balance = Decimal('154250.00')
    running_balance = opening_balance
    total_debits = Decimal('0.00')
    total_credits = Decimal('0.00')

    table_data = [
        [
            Paragraph('<b>Post Date</b>', ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=colors.white)),
            Paragraph('<b>Value Date</b>', ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=colors.white)),
            Paragraph('<b>Narration</b>', ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=colors.white)),
            Paragraph('<b>Ref/Cheque No.</b>', ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=colors.white)),
            Paragraph('<b>Debits</b>', ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=colors.white, alignment=2)),
            Paragraph('<b>Credits</b>', ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=colors.white, alignment=2)),
            Paragraph('<b>Balance</b>', ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=colors.white, alignment=2)),
        ]
    ]

    cell_style = ParagraphStyle('TD', fontName='Helvetica', fontSize=6.5, leading=8, textColor=colors.HexColor('#1f2937'))
    debit_style = ParagraphStyle('TDDeb', fontName='Helvetica-Bold', fontSize=6.5, leading=8, textColor=colors.HexColor('#d32f2f'), alignment=2)
    credit_style = ParagraphStyle('TDCr', fontName='Helvetica-Bold', fontSize=6.5, leading=8, textColor=colors.HexColor('#15803d'), alignment=2)
    bal_style = ParagraphStyle('TDBal', fontName='Helvetica', fontSize=6.5, leading=8, textColor=colors.HexColor('#111827'), alignment=2)

    for post_dt, val_dt, narr, ref_no, deb, cr in raw_txns:
        running_balance = running_balance - deb + cr
        total_debits += deb
        total_credits += cr

        deb_str = f"{deb:,.2f}" if deb > 0 else "-"
        cr_str = f"{cr:,.2f}" if cr > 0 else "-"
        bal_str = f"{running_balance:,.2f}"

        deb_p = Paragraph(deb_str, debit_style) if deb > 0 else Paragraph("-", cell_style)
        cr_p = Paragraph(cr_str, credit_style) if cr > 0 else Paragraph("-", cell_style)
        bal_p = Paragraph(bal_str, bal_style)

        table_data.append([
            Paragraph(post_dt, cell_style),
            Paragraph(val_dt, cell_style),
            Paragraph(narr, cell_style),
            Paragraph(ref_no, cell_style),
            deb_p,
            cr_p,
            bal_p
        ])

    closing_balance = running_balance

    doc = SimpleDocTemplate(
        output_filename,
        pagesize=letter,
        leftMargin=26,
        rightMargin=26,
        topMargin=26,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    elements = []

    # 1. Top Header: Access logo & statement title
    brand_logo = Paragraph(
        '<font size=18 color="#f05a22">◆</font> <font size=16 color="#001b44"><b>access</b></font>',
        ParagraphStyle('Brand', parent=styles['Normal'], alignment=2)
    )

    title_para = Paragraph(
        '<font color="#f05a22" size=12><b>YOUR ACCOUNT STATEMENT</b></font><br/>'
        '<font color="#111827" size=10><b>Account Details</b></font>',
        ParagraphStyle('Title', parent=styles['Normal'])
    )

    top_table = Table([[title_para, brand_logo]], colWidths=[380, 180])
    top_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(top_table)
    elements.append(Spacer(1, 4))

    # 2. Account Details Key-Values
    lbl_style = ParagraphStyle('Lbl', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, textColor=colors.HexColor('#111827'))
    v_style = ParagraphStyle('Val', fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=colors.HexColor('#374151'))

    acc_details = [
        [
            Paragraph("Account Number:", lbl_style),
            Paragraph("142****885", v_style),
            Paragraph("Statement Period:", lbl_style),
            Paragraph("01/10/2026 - 31/10/2026", v_style)
        ],
        [
            Paragraph("Account Name:", lbl_style),
            Paragraph("ADEFEMI LOGISTICS & CONSULTING LTD", v_style),
            Paragraph("Currency:", lbl_style),
            Paragraph("NGN", v_style)
        ],
        [
            Paragraph("Product Name:", lbl_style),
            Paragraph("ACCESS CURRENT ACCOUNT - CORPORATE", v_style),
            Paragraph("Opening Balance:", lbl_style),
            Paragraph(f"₦{opening_balance:,.2f}", v_style)
        ],
        [
            Paragraph("Branch:", lbl_style),
            Paragraph("Adetokunbo Ademola Branch, VI, Lagos", v_style),
            Paragraph("Closing Balance:", lbl_style),
            Paragraph(f"<b>₦{closing_balance:,.2f}</b>", lbl_style)
        ]
    ]

    details_table = Table(acc_details, colWidths=[90, 190, 95, 185])
    details_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 8))

    # 3. Overview Summary Table
    overview_header_style = ParagraphStyle('OVH', fontName='Helvetica-Bold', fontSize=6.5, textColor=colors.HexColor('#374151'))
    overview_cell_style = ParagraphStyle('OVC', fontName='Helvetica', fontSize=7, textColor=colors.HexColor('#111827'))

    overview_rows = [
        [
            Paragraph("<b>Account No</b>", overview_header_style),
            Paragraph("<b>Product Name</b>", overview_header_style),
            Paragraph("<b>Currency</b>", overview_header_style),
            Paragraph("<b>Opening Balance</b>", overview_header_style),
            Paragraph("<b>Debits</b>", overview_header_style),
            Paragraph("<b>Credits</b>", overview_header_style),
            Paragraph("<b>Closing Balance</b>", overview_header_style),
        ],
        [
            Paragraph("142****885", overview_cell_style),
            Paragraph("ACCESS CURRENT", overview_cell_style),
            Paragraph("NGN", overview_cell_style),
            Paragraph(f"{opening_balance:,.2f}", overview_cell_style),
            Paragraph(f"{total_debits:,.2f}", overview_cell_style),
            Paragraph(f"{total_credits:,.2f}", overview_cell_style),
            Paragraph(f"<b>{closing_balance:,.2f}</b>", overview_cell_style),
        ]
    ]
    overview_table = Table(overview_rows, colWidths=[70, 95, 55, 85, 85, 85, 85])
    overview_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e5e7eb')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f9fafb')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
    ]))
    elements.append(overview_table)
    elements.append(Spacer(1, 10))

    # 4. Main Transactions Table
    txn_table = Table(
        table_data,
        colWidths=[45, 45, 185, 105, 58, 58, 64],
        repeatRows=1
    )

    table_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ea580c')),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
        ('TOPPADDING', (0, 0), (-1, 0), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#fed7aa')),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#fed7aa')),
    ]

    for i in range(1, len(table_data)):
        bg = colors.HexColor('#ffffff') if i % 2 == 1 else colors.HexColor('#fff7ed')
        table_styles.append(('BACKGROUND', (0, i), (-1, i), bg))
        table_styles.append(('TOPPADDING', (0, i), (-1, i), 2.5))
        table_styles.append(('BOTTOMPADDING', (0, i), (-1, i), 2.5))

    txn_table.setStyle(TableStyle(table_styles))
    elements.append(txn_table)

    doc.build(elements, canvasmaker=AccessNumberedCanvas)

    print(f"Generated {output_filename} successfully!")
    print(f"Total Transactions: {len(raw_txns)}")
    print(f"Opening Balance:    NGN {opening_balance:,.2f}")
    print(f"Total Credits:      NGN {total_credits:,.2f}")
    print(f"Total Debits:       NGN {total_debits:,.2f}")
    print(f"Closing Balance:    NGN {closing_balance:,.2f}")
    print(f"Math Balances Out:  {opening_balance + total_credits - total_debits == closing_balance}")

if __name__ == '__main__':
    generate_access_statement()
