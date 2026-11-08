import io
from datetime import datetime
from typing import Any

from app.db.models import Quote, Lead, BusinessProfile
from app.catalogue.loader import load_catalogue

catalogue = load_catalogue()


def generate_quote_html(quote: Quote, lead: Lead | None = None, profile: BusinessProfile | None = None) -> str:
    biz_name = profile.business_type if profile and profile.business_type else "Enterprise Business Customer"
    city = profile.city if profile and profile.city else "India"
    date_str = quote.created_at.strftime("%d %B %Y")

    lines_html = ""
    for idx, line in enumerate(quote.lines, 1):
        prod = catalogue.get(line.product_id)
        pname = prod.name if prod else line.product_id
        lines_html += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">{idx}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">
                <strong>{pname}</strong> <span style="color: #64748b; font-size: 12px;">({line.product_id})</span>
            </td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: center;">{line.qty}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right;">INR {line.unit_price:,}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right;">INR {line.line_monthly:,}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right;">INR {line.setup:,}</td>
        </tr>
        """

    savings_row = ""
    if quote.savings_vs_current:
        savings_row = f"""
        <div style="background-color: #ecfdf5; border-left: 4px solid #10b981; padding: 12px; margin-top: 15px; border-radius: 4px;">
            <strong style="color: #065f46;">Estimated Monthly Savings:</strong>
            <span style="color: #047857; font-size: 16px; font-weight: bold;"> INR {quote.savings_vs_current:,} / month</span>
            <span style="color: #065f46; font-size: 13px;"> (Annualized: INR {quote.savings_vs_current * 12:,})</span>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Accel Business Digital Bundle Quote - {quote.id}</title>
        <style>
            body {{
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                margin: 40px;
                color: #1e293b;
                line-height: 1.5;
            }}
            .header {{
                display: flex;
                justify-content: space-between;
                border-bottom: 3px solid #e11d48;
                padding-bottom: 20px;
                margin-bottom: 25px;
            }}
            .brand {{
                font-size: 26px;
                font-weight: 800;
                color: #e11d48;
                letter-spacing: -0.5px;
            }}
            .badge {{
                display: inline-block;
                padding: 4px 10px;
                background-color: #f1f5f9;
                color: #475569;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            th {{
                background-color: #f8fafc;
                padding: 12px 10px;
                text-align: left;
                font-size: 13px;
                font-weight: 700;
                color: #475569;
                border-bottom: 2px solid #cbd5e1;
            }}
            .totals-table {{
                width: 350px;
                margin-left: auto;
                margin-top: 25px;
            }}
            .totals-table td {{
                padding: 6px 10px;
            }}
            .signatory-box {{
                margin-top: 50px;
                border-top: 1px dashed #cbd5e1;
                padding-top: 20px;
                display: flex;
                justify-content: space-between;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div>
                <div class="brand">accel business</div>
                <div style="font-size: 13px; color: #64748b;">Project Udyam Digital - Official Service Quote</div>
            </div>
            <div style="text-align: right;">
                <div class="badge">VERSION {quote.version}</div>
                <div style="font-size: 13px; color: #64748b; margin-top: 5px;">Quote Ref: #{str(quote.id)[:8]}</div>
                <div style="font-size: 13px; color: #64748b;">Date: {date_str}</div>
            </div>
        </div>

        <div style="margin-bottom: 20px;">
            <strong style="font-size: 16px;">Prepared For:</strong>
            <div style="color: #334155; font-size: 14px;">{biz_name}</div>
            <div style="color: #64748b; font-size: 13px;">Location: {city} | Contract Commitment: {quote.term_months} Months</div>
        </div>

        <table>
            <thead>
                <tr>
                    <th style="width: 5%;">#</th>
                    <th style="width: 45%;">Digital Solution / Service</th>
                    <th style="width: 10%; text-align: center;">Qty</th>
                    <th style="width: 15%; text-align: right;">Unit Price</th>
                    <th style="width: 15%; text-align: right;">Monthly Recurring</th>
                    <th style="width: 10%; text-align: right;">One-time Setup</th>
                </tr>
            </thead>
            <tbody>
                {lines_html}
            </tbody>
        </table>

        <table class="totals-table">
            <tr>
                <td style="color: #475569;">Monthly Recurring Total:</td>
                <td style="text-align: right; font-weight: bold;">INR {quote.monthly_recurring:,}</td>
            </tr>
            <tr>
                <td style="color: #475569;">One-Time Activation / Setup:</td>
                <td style="text-align: right; font-weight: bold;">INR {quote.one_time:,}</td>
            </tr>
            <tr style="border-top: 2px solid #e2e8f0; font-size: 16px; color: #0f172a;">
                <td><strong>First Month Payable:</strong></td>
                <td style="text-align: right; font-weight: 800; color: #e11d48;">INR {quote.first_month_total:,}</td>
            </tr>
        </table>

        {savings_row}

        <div class="signatory-box">
            <div>
                <p style="font-size: 12px; color: #64748b; margin-bottom: 40px;">Authorized Signatory (Accel Enterprise)</p>
                <div style="border-top: 1px solid #94a3b8; width: 200px;"></div>
                <p style="font-size: 11px; color: #94a3b8; margin-top: 4px;">Digitally Verified & Stamped</p>
            </div>
            <div style="text-align: right;">
                <p style="font-size: 12px; color: #64748b; margin-bottom: 40px;">Customer Acceptance (e-Sign)</p>
                <div style="border-top: 1px solid #94a3b8; width: 200px; margin-left: auto;"></div>
                <p style="font-size: 11px; color: #94a3b8; margin-top: 4px;">Aadhaar / OTP Verified Signatory</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def generate_quote_pdf_bytes(quote: Quote, lead: Lead | None = None, profile: BusinessProfile | None = None) -> bytes:
    """Generates official PDF quote bytes via WeasyPrint, falling back to ReportLab if Pango DLL is absent."""
    html = generate_quote_html(quote, lead, profile)

    # 1. Attempt WeasyPrint
    try:
        from weasyprint import HTML
        return HTML(string=html).write_pdf()
    except (ImportError, OSError):
        pass

    # 2. Robust fallback using reportlab
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    story = []

    # Title
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=colors.HexColor("#e11d48"),
        spaceAfter=6,
    )
    story.append(Paragraph("accel business", title_style))
    story.append(Paragraph(f"Project Udyam Digital - Official Service Quote (Version {quote.version})", styles["Normal"]))
    story.append(Spacer(1, 15))

    # Details
    biz_name = profile.business_type if profile and profile.business_type else "Enterprise Business Customer"
    story.append(Paragraph(f"<b>Customer:</b> {biz_name} | <b>Commitment:</b> {quote.term_months} Months", styles["Normal"]))
    story.append(Spacer(1, 15))

    # Table of lines
    data = [["#", "Product", "Qty", "Unit Price", "Monthly", "Setup"]]
    for idx, l in enumerate(quote.lines, 1):
        prod = catalogue.get(l.product_id)
        pname = prod.name if prod else l.product_id
        data.append([
            str(idx),
            f"{pname} ({l.product_id})",
            str(l.qty),
            f"INR {l.unit_price:,}",
            f"INR {l.line_monthly:,}",
            f"INR {l.setup:,}",
        ])

    data.append(["", "", "", "Monthly Recurring Total:", f"INR {quote.monthly_recurring:,}", ""])
    data.append(["", "", "", "One-Time Setup:", f"INR {quote.one_time:,}", ""])
    data.append(["", "", "", "First Month Total:", f"INR {quote.first_month_total:,}", ""])

    t = Table(data, colWidths=[25, 230, 35, 80, 85, 80])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#475569")),
        ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -4), 0.5, colors.HexColor("#cbd5e1")),
        ("FONTNAME", (3, -3), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (3, -1), (-1, -1), colors.HexColor("#e11d48")),
    ]))
    story.append(t)

    if quote.savings_vs_current:
        story.append(Spacer(1, 15))
        story.append(Paragraph(
            f"<b>Estimated Monthly Savings:</b> INR {quote.savings_vs_current:,} / month "
            f"(Annualized: INR {quote.savings_vs_current * 12:,})",
            styles["Normal"],
        ))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
