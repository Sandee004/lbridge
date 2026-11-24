import os
from decimal import Decimal
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont('Helvetica', 8)
        self.setFillColor(colors.HexColor('#6b7280'))
        self.drawString(36, 25, 'MERIDIAN COMMERCIAL BANK • OFFICIAL ACCOUNT STATEMENT • CONFIDENTIAL')
        page_str = f'Page {self._pageNumber} of {page_count}'
        self.drawRightString(612 - 36, 25, page_str)
        self.restoreState()

def generate_pdf(output_filename="demo_statement.pdf"):
    transactions_data = [
        ('01/11/2026', 'AWS CLOUD SERVICES SEATTLE WA', Decimal('245.80'), Decimal('0.00')),
        ('01/11/2026', 'TRF/FRM/0029103994/REF88219', Decimal('0.00'), Decimal('3500.00')),
        ('02/11/2026', 'GOOGLE WORKSPACE CLOUD GSUITE', Decimal('72.00'), Decimal('0.00')),
        ('02/11/2026', 'POS 4910283 WTH TRF', Decimal('18.50'), Decimal('0.00')),
        ('03/11/2026', 'WIRE IN: ACME CORP INVOICE #10492', Decimal('0.00'), Decimal('12500.00')),
        ('03/11/2026', 'UBER TRIP 11/02 SAN FRANCISCO CA', Decimal('42.30'), Decimal('0.00')),
        ('04/11/2026', 'NIP/UBN/CHINEDU OKAFOR/PAYMENT', Decimal('850.00'), Decimal('0.00')),
        ('04/11/2026', 'GITHUB ENTERPRISE SUBSCRIPTION', Decimal('84.00'), Decimal('0.00')),
        ('05/11/2026', 'ATM WDL 0482910 CENTRAL ST', Decimal('300.00'), Decimal('0.00')),
        ('05/11/2026', 'STRIPE PAYOUT SALES OCT-NOV', Decimal('0.00'), Decimal('8420.50')),
        ('06/11/2026', 'HEROKU PLATFORM SERVICES', Decimal('125.00'), Decimal('0.00')),
        ('06/11/2026', 'CASH DEP AT BRANCH #042', Decimal('0.00'), Decimal('1500.00')),
        ('07/11/2026', 'DIRECT DEBIT DDA REF 990182', Decimal('450.00'), Decimal('0.00')),
        ('08/11/2026', 'SLACK TECHNOLOGIES INC MONTHLY', Decimal('150.00'), Decimal('0.00')),
        ('08/11/2026', 'FEE 001928', Decimal('15.00'), Decimal('0.00')),
        ('09/11/2026', 'APPLE STORE SOHO NY - MACBOOK PRO', Decimal('2499.00'), Decimal('0.00')),
        ('10/11/2026', 'DIRECT DEPOSIT: VERTEX CLIENT RETAINER', Decimal('0.00'), Decimal('6000.00')),
        ('10/11/2026', 'ZOOM VIDEO COMMUNICATIONS', Decimal('29.99'), Decimal('0.00')),
        ('11/11/2026', 'MISC PYMT 9910482', Decimal('135.50'), Decimal('0.00')),
        ('11/11/2026', 'STAPLES OFFICE SUPPLIES #104', Decimal('184.20'), Decimal('0.00')),
        ('12/11/2026', 'TERM LOAN REPAYMENT ACCT 9821', Decimal('1200.00'), Decimal('0.00')),
        ('12/11/2026', 'BILL PMT 109384729', Decimal('210.00'), Decimal('0.00')),
        ('13/11/2026', 'INWARD WIRE: GLOBAL VENTURES', Decimal('0.00'), Decimal('15000.00')),
        ('14/11/2026', 'BOLT RIDE TRIP 8812', Decimal('24.80'), Decimal('0.00')),
        ('14/11/2026', 'TRANSFER TO 994019201', Decimal('500.00'), Decimal('0.00')),
        ('15/11/2026', 'DIRECTOR EQUITY INJECTION - T. VANCE', Decimal('0.00'), Decimal('10000.00')),
        ('15/11/2026', 'PAYROLL BATCH RUN NOV 15', Decimal('8450.00'), Decimal('0.00')),
        ('16/11/2026', 'MOBILE TRANSFER / 8839201', Decimal('75.00'), Decimal('0.00')),
        ('16/11/2026', 'MAILCHIMP EMAIL MARKETING', Decimal('89.00'), Decimal('0.00')),
        ('17/11/2026', 'REFUND: AWS INC OVERPAYMENT', Decimal('0.00'), Decimal('65.00')),
        ('17/11/2026', 'CHECK #1042', Decimal('620.00'), Decimal('0.00')),
        ('18/11/2026', 'STARBUCKS STORE 08492 NEW YORK', Decimal('16.45'), Decimal('0.00')),
        ('18/11/2026', 'CLIENT SETTLEMENT INVOICE #881', Decimal('0.00'), Decimal('4250.00')),
        ('19/11/2026', 'DEBIT MEMO #99102', Decimal('35.00'), Decimal('0.00')),
        ('19/11/2026', 'DELTA AIR LINES FLIGHT 482', Decimal('580.40'), Decimal('0.00')),
        ('20/11/2026', 'OFFICE INTERNET FIBER ACCESS', Decimal('120.00'), Decimal('0.00')),
        ('20/11/2026', 'SETTLEMENT 90184-B', Decimal('0.00'), Decimal('1800.00')),
        ('21/11/2026', 'NOTION LABS INC ANNUAL', Decimal('192.00'), Decimal('0.00')),
        ('21/11/2026', 'POS PURCHASE BAKERY 49102', Decimal('28.50'), Decimal('0.00')),
        ('22/11/2026', 'TRF TO SAVINGS ACCT 048291-02', Decimal('3000.00'), Decimal('0.00')),
        ('23/11/2026', 'STRIPE PAYOUT SALES WEEK 47', Decimal('0.00'), Decimal('7640.20')),
        ('23/11/2026', 'FIGMA SUBSCRIPTION DESIGN TEAM', Decimal('45.00'), Decimal('0.00')),
        ('24/11/2026', 'CLEANING SERVICE OFFICE SPACES', Decimal('250.00'), Decimal('0.00')),
        ('24/11/2026', 'TRF/REF/9910492810/UNSPECIFIED', Decimal('150.00'), Decimal('0.00')),
        ('25/11/2026', 'CONSULTING REVENUE - TECHCORP', Decimal('0.00'), Decimal('9500.00')),
        ('25/11/2026', 'UBER EATS TEAM LUNCH', Decimal('112.60'), Decimal('0.00')),
        ('26/11/2026', 'EQUIPMENT LEASE OFFICE COPIER', Decimal('340.00'), Decimal('0.00')),
        ('26/11/2026', 'NIP TRF / QUICK DISBURSEMENT', Decimal('420.00'), Decimal('0.00')),
        ('27/11/2026', 'DOMESTIC WIRE TRANSFER FEE', Decimal('25.00'), Decimal('0.00')),
        ('27/11/2026', 'OWNER DRAWING TRANSFER TO PERSONAL', Decimal('2500.00'), Decimal('0.00')),
        ('28/11/2026', 'MERCHANT DEPOSIT POINT OF SALE', Decimal('0.00'), Decimal('3210.00')),
        ('28/11/2026', 'CANVA SUBSCRIPTION GRAPHICS', Decimal('30.00'), Decimal('0.00')),
        ('29/11/2026', 'MONTHLY ACCOUNT MAINTENANCE FEE', Decimal('35.00'), Decimal('0.00')),
        ('29/11/2026', 'TAX CONSULTANT ADVISORY PYMT', Decimal('800.00'), Decimal('0.00')),
        ('30/11/2026', 'INTEREST PAID FOR NOV 2026', Decimal('0.00'), Decimal('48.75')),
        ('30/11/2026', 'CLOUD STORAGE BACKUP ARCHIVE', Decimal('19.99'), Decimal('0.00'))
    ]

    opening_balance = Decimal('42500.00')
    running_balance = opening_balance
    total_debits = Decimal('0.00')
    total_credits = Decimal('0.00')

    for dt, desc, deb, cr in transactions_data:
        running_balance = running_balance - deb + cr
        total_debits += deb
        total_credits += cr

    closing_balance = running_balance

    doc = SimpleDocTemplate(
        output_filename,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'BankTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f2942')
    )
    subtitle_style = ParagraphStyle(
        'BankSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#4b5563')
    )
    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#374151')
    )
    val_style = ParagraphStyle(
        'ValStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#111827')
    )
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor('#1f2937')
    )
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white
    )

    elements = []

    # Bank Header
    header_data = [
        [
            Paragraph('<b>MERIDIAN COMMERCIAL BANK</b><br/><font size=8 color="#6b7280">Head Office: 450 Financial Way, Suite 800, New York, NY 10005<br/>Swift: MCBNUS33 • support@meridianbank.com • (800) 555-0199</font>', title_style),
            Paragraph('<font size=12><b>ACCOUNT STATEMENT</b></font><br/><font size=8 color="#4b5563">Date Issued: 01 Dec 2026<br/>Currency: USD ($)</font>', subtitle_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[360, 180])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 14))

    # Account Info
    account_info = [
        [
            Paragraph('<b>ACCOUNT HOLDER:</b>', label_style),
            Paragraph('NOVATECH ENTERPRISES LLC', val_style),
            Paragraph('<b>STATEMENT PERIOD:</b>', label_style),
            Paragraph('01/11/2026 - 30/11/2026', val_style)
        ],
        [
            Paragraph('<b>ACCOUNT NUMBER:</b>', label_style),
            Paragraph('0482910492', val_style),
            Paragraph('<b>ACCOUNT TYPE:</b>', label_style),
            Paragraph('Commercial Corporate Checking', val_style)
        ],
        [
            Paragraph('<b>BRANCH:</b>', label_style),
            Paragraph('Manhattan Commercial Hub', val_style),
            Paragraph('<b>SORT CODE / ROUTING:</b>', label_style),
            Paragraph('021000021', val_style)
        ]
    ]
    acc_table = Table(account_info, colWidths=[110, 160, 120, 150])
    acc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#edf2f7')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(acc_table)
    elements.append(Spacer(1, 10))

    # Summary Metrics
    summary_data = [
        [
            Paragraph('<b>Opening Balance</b>', label_style),
            Paragraph('<b>Total Credits (Deposits)</b>', label_style),
            Paragraph('<b>Total Debits (Withdrawals)</b>', label_style),
            Paragraph('<b>Closing Balance</b>', label_style)
        ],
        [
            Paragraph(f'${opening_balance:,.2f}', val_style),
            Paragraph(f'+${total_credits:,.2f}', val_style),
            Paragraph(f'-${total_debits:,.2f}', val_style),
            Paragraph(f'<b>${closing_balance:,.2f}</b>', val_style)
        ]
    ]
    summary_table = Table(summary_data, colWidths=[135, 135, 135, 135])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eff6ff')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#bfdbfe')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dbeafe')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 14))

    # Transaction Table Header
    txn_rows = [
        [
            Paragraph('<b>Date</b>', table_header_style),
            Paragraph('<b>Description / Narration</b>', table_header_style),
            Paragraph('<b>Debit ($)</b>', table_header_style),
            Paragraph('<b>Credit ($)</b>', table_header_style),
            Paragraph('<b>Balance ($)</b>', table_header_style)
        ]
    ]

    running_balance = opening_balance
    for row_idx, (dt, desc, deb, cr) in enumerate(transactions_data):
        running_balance = running_balance - deb + cr
        deb_str = f'{deb:,.2f}' if deb > 0 else '-'
        cr_str = f'{cr:,.2f}' if cr > 0 else '-'
        bal_str = f'{running_balance:,.2f}'

        txn_rows.append([
            Paragraph(dt, table_cell_style),
            Paragraph(desc, table_cell_style),
            Paragraph(deb_str, table_cell_style),
            Paragraph(cr_str, table_cell_style),
            Paragraph(bal_str, table_cell_style)
        ])

    txn_table = Table(
        txn_rows,
        colWidths=[65, 235, 75, 75, 90],
        repeatRows=1
    )

    table_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f2942')),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('TOPPADDING', (0, 0), (-1, 0), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
    ]

    for i in range(1, len(txn_rows)):
        bg = colors.HexColor('#ffffff') if i % 2 == 1 else colors.HexColor('#f9fafb')
        table_styles.append(('BACKGROUND', (0, i), (-1, i), bg))
        table_styles.append(('TOPPADDING', (0, i), (-1, i), 3))
        table_styles.append(('BOTTOMPADDING', (0, i), (-1, i), 3))

    txn_table.setStyle(TableStyle(table_styles))
    elements.append(txn_table)

    doc.build(elements, canvasmaker=NumberedCanvas)
    print(f'Generated {output_filename} successfully with {len(transactions_data)} transactions.')

if __name__ == '__main__':
    generate_pdf()
