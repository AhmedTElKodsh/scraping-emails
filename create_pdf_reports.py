#!/usr/bin/env python3
"""
Create professional PDF reports for client presentation
Converts markdown reports to beautifully formatted PDFs with Arabic support
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import sqlite3
import json

def setup_arabic_font():
    """Setup Arabic font support"""
    # Try to use system Arabic fonts
    try:
        # For Windows, try Arial which supports Arabic
        pdfmetrics.registerFont(TTFont('Arabic', 'arial.ttf'))
        return True
    except:
        try:
            # Try alternative
            pdfmetrics.registerFont(TTFont('Arabic', 'C:/Windows/Fonts/arial.ttf'))
            return True
        except:
            print("⚠️  Arabic font not found, using default font")
            return False

def get_property_data():
    """Extract property data from database"""
    conn = sqlite3.connect('data/farida.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT data_json FROM app_properties")
    rows = cursor.fetchall()
    
    properties = []
    for row in rows:
        try:
            data_json = json.loads(row[0])
            payload = data_json.get('payload', {})
            properties_array = payload.get('data', [])
            
            for prop in properties_array:
                from datetime import datetime as dt
                
                # Parse date
                publish_time = prop.get('publish_time', '')
                if publish_time:
                    try:
                        date_obj = dt.fromisoformat(publish_time.replace('Z', '+00:00'))
                        opportunity_date = date_obj.strftime('%Y-%m-%d')
                    except:
                        opportunity_date = publish_time
                else:
                    opportunity_date = "غير محدد"
                
                # Calculate total value
                schedules = prop.get('payment_schedules', {})
                down_payments = schedules.get('down_payments', [])
                installments = schedules.get('installments', [])
                
                total_down = sum(dp.get('amount', 0) for dp in down_payments)
                total_installments = sum(
                    inst.get('amount', 0) 
                    for inst in installments 
                    if inst.get('type') == 'installment'
                )
                total_value = total_down + total_installments
                
                properties.append({
                    'id': prop.get('id'),
                    'date': opportunity_date,
                    'name': prop.get('title', 'Unknown'),
                    'location': prop.get('location', 'Unknown'),
                    'type': f"{prop.get('property_type', 'Unknown')} - {prop.get('property_sub_type', '')}",
                    'down_payment': prop.get('down_payment', 0),
                    'installment': prop.get('installment', 0),
                    'installments_count': prop.get('installments_count', 0),
                    'total_value': total_value,
                    'currency': prop.get('currency', 'EGP'),
                    'total_shares': prop.get('total_shares', 0),
                    'available_shares': prop.get('available_shares', 0),
                    'sold_shares': prop.get('sold_shares', 0),
                    'funding_status': prop.get('funding_status', 'unknown'),
                    'delivery_date': prop.get('delivery_date', 'غير محدد'),
                    'exit_date': prop.get('exit_date', 'غير محدد')
                })
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    conn.close()
    return properties

def create_arabic_properties_pdf():
    """Create PDF for Arabic properties summary"""
    print("📄 Creating Arabic Properties PDF...")
    
    properties = get_property_data()
    
    # Create PDF
    pdf_file = '_bmad-output/farida-properties-report.pdf'
    doc = SimpleDocTemplate(pdf_file, pagesize=landscape(A4),
                           rightMargin=1*cm, leftMargin=1*cm,
                           topMargin=1.5*cm, bottomMargin=1.5*cm)
    
    # Container for elements
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Heading style
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    # Add title
    elements.append(Paragraph("Farida Estate Investment Opportunities Report", title_style))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Statistics
    total_shares = sum(p['total_shares'] for p in properties)
    available_shares = sum(p['available_shares'] for p in properties)
    sold_shares = sum(p['sold_shares'] for p in properties)
    sales_rate = (sold_shares / total_shares * 100) if total_shares > 0 else 0
    
    stats_data = [
        ['Metric', 'Value'],
        ['Total Properties', str(len(properties))],
        ['Total Shares', f'{total_shares:,}'],
        ['Available Shares', f'{available_shares:,}'],
        ['Sold Shares', f'{sold_shares:,}'],
        ['Sales Rate', f'{sales_rate:.1f}%']
    ]
    
    stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(stats_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Properties table
    elements.append(Paragraph("Investment Opportunities Overview", heading_style))
    elements.append(Spacer(1, 0.1*inch))
    
    # Table headers
    table_data = [
        ['#', 'ID', 'Date', 'Property Name', 'Location', 'Type', 'Total Value', 'Status']
    ]
    
    # Add property rows
    for i, prop in enumerate(properties, 1):
        table_data.append([
            str(i),
            str(prop['id']),
            prop['date'],
            prop['name'][:30] + '...' if len(prop['name']) > 30 else prop['name'],
            prop['location'][:20] + '...' if len(prop['location']) > 20 else prop['location'],
            prop['type'][:20] + '...' if len(prop['type']) > 20 else prop['type'],
            f"{prop['total_value']:,.0f} {prop['currency']}",
            prop['funding_status']
        ])
    
    # Create table
    prop_table = Table(table_data, colWidths=[0.5*inch, 0.6*inch, 1*inch, 2.2*inch, 1.8*inch, 1.5*inch, 1.2*inch, 0.9*inch])
    prop_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))
    
    elements.append(prop_table)
    
    # Build PDF
    doc.build(elements)
    print(f"✓ Created: {pdf_file}")
    return pdf_file

def create_visual_analytics_pdf():
    """Create PDF for visual analytics report with charts"""
    print("📊 Creating Visual Analytics PDF...")
    
    properties = get_property_data()
    
    # Create PDF
    pdf_file = '_bmad-output/farida-visual-analytics-report.pdf'
    doc = SimpleDocTemplate(pdf_file, pagesize=A4,
                           rightMargin=2*cm, leftMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold'
    )
    
    # Title page
    elements.append(Spacer(1, 2*inch))
    elements.append(Paragraph("Farida Estate", title_style))
    elements.append(Paragraph("Visual Analytics Report", title_style))
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    elements.append(Paragraph("Prepared for: Mohamed Sabry", styles['Normal']))
    elements.append(PageBreak())
    
    # Executive Summary
    elements.append(Paragraph("Executive Summary", heading_style))
    
    total_shares = sum(p['total_shares'] for p in properties)
    available_shares = sum(p['available_shares'] for p in properties)
    sold_shares = sum(p['sold_shares'] for p in properties)
    sales_rate = (sold_shares / total_shares * 100) if total_shares > 0 else 0
    avg_value = sum(p['total_value'] for p in properties) / len(properties) if properties else 0
    
    summary_text = f"""
    This report provides a comprehensive visual analysis of {len(properties)} investment properties 
    available on the Farida Estate platform. Key findings include:
    <br/><br/>
    • Total investment opportunities: {len(properties)} properties<br/>
    • Market penetration: {sales_rate:.1f}% of shares sold<br/>
    • Average investment value: {avg_value:,.0f} EGP<br/>
    • Available opportunities: {sum(1 for p in properties if p['funding_status'] == 'available')} properties<br/>
    <br/>
    The following pages present detailed visualizations and insights to support investment decisions.
    """
    
    elements.append(Paragraph(summary_text, styles['BodyText']))
    elements.append(PageBreak())
    
    # Add charts
    chart_files = [
        ('Funding Status Distribution', 'funding_status.png'),
        ('Market Shares Overview', 'shares_availability.png'),
        ('Property Type Distribution', 'property_types.png'),
        ('Investment Value Distribution', 'value_distribution.png'),
        ('Top 10 Properties by Value', 'top_properties.png'),
        ('Share Availability Heatmap', 'availability_heatmap.png')
    ]
    
    for title, filename in chart_files:
        elements.append(Paragraph(title, heading_style))
        
        chart_path = f'_bmad-output/charts/{filename}'
        if os.path.exists(chart_path):
            img = Image(chart_path, width=6*inch, height=3*inch)
            elements.append(img)
        else:
            elements.append(Paragraph(f"Chart not found: {filename}", styles['Normal']))
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Add page break after every 2 charts
        if chart_files.index((title, filename)) % 2 == 1:
            elements.append(PageBreak())
    
    # Investment Insights
    elements.append(Paragraph("Investment Insights", heading_style))
    
    available_props = sum(1 for p in properties if p['funding_status'] == 'available')
    funded_props = sum(1 for p in properties if p['funding_status'] == 'funded')
    
    insights_text = f"""
    <b>Market Opportunities:</b><br/>
    • {available_props} properties currently available for investment ({available_props/len(properties)*100:.1f}%)<br/>
    • {funded_props} properties fully funded ({funded_props/len(properties)*100:.1f}%)<br/>
    <br/>
    <b>Investment Characteristics:</b><br/>
    • Average property value: {avg_value:,.0f} EGP<br/>
    • Total market capitalization: {sum(p['total_value'] for p in properties):,.0f} EGP<br/>
    • Share liquidity: {available_shares:,} shares available for purchase<br/>
    <br/>
    <b>Recommendations:</b><br/>
    • Diversify across multiple property types<br/>
    • Consider both short-term and long-term investment horizons<br/>
    • Monitor funding status for high-demand properties<br/>
    • Review exit dates to align with investment goals<br/>
    """
    
    elements.append(Paragraph(insights_text, styles['BodyText']))
    
    # Build PDF
    doc.build(elements)
    print(f"✓ Created: {pdf_file}")
    return pdf_file

def main():
    print("📑 Creating professional PDF reports for client presentation...\n")
    
    # Check if charts exist
    if not os.path.exists('_bmad-output/charts'):
        print("⚠️  Charts directory not found. Please run create_visual_charts.py first.")
        return
    
    # Create PDFs
    pdf1 = create_arabic_properties_pdf()
    pdf2 = create_visual_analytics_pdf()
    
    print("\n✅ PDF reports created successfully!")
    print("\nGenerated files:")
    print(f"  1. {pdf1}")
    print(f"  2. {pdf2}")
    print("\n📧 These PDFs are ready for client presentation!")

if __name__ == "__main__":
    main()
