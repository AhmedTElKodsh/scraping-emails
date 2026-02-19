#!/usr/bin/env python3
"""
Create detailed property report for client with Arabic field names
Extracts: تاريخ الفرصة، اسم الفرصة، المنطقة، مساحة العقار، قيمة الحصة، إجمالي قيمة العقار
"""

import sqlite3
import json
import csv
from datetime import datetime

def calculate_total_property_value(property_data):
    """Calculate total property value from share price and total shares"""
    try:
        # Try to get from payment schedules
        schedules = property_data.get('payment_schedules', {})
        down_payments = schedules.get('down_payments', [])
        installments = schedules.get('installments', [])
        
        # Sum all payments
        total = 0
        for dp in down_payments:
            total += dp.get('amount', 0)
        for inst in installments:
            if inst.get('type') == 'installment':
                total += inst.get('amount', 0)
        
        return total if total > 0 else None
    except:
        return None

def extract_property_size(property_data):
    """Extract property size from various possible fields"""
    # Check common size fields
    size_fields = ['size', 'area', 'property_size', 'built_area', 'land_area']
    for field in size_fields:
        if field in property_data and property_data[field]:
            return property_data[field]
    return "غير محدد"

def main():
    # Connect to database
    conn = sqlite3.connect('data/farida.db')
    cursor = conn.cursor()
    
    # Get all properties
    cursor.execute("SELECT * FROM app_properties")
    rows = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    
    print(f"Found {len(rows)} properties in database")
    
    # Prepare data for CSV and analysis
    properties_data = []
    
    for row in rows:
        property_dict = dict(zip(columns, row))
        
        # Parse JSON fields
        try:
            property_json = json.loads(property_dict.get('property_json', '{}'))
        except:
            property_json = {}
        
        # Extract required fields
        property_id = property_dict.get('property_id', 'N/A')
        
        # تاريخ الفرصة (Opportunity Date) - publish_time
        publish_time = property_json.get('publish_time', '')
        if publish_time:
            try:
                dt = datetime.fromisoformat(publish_time.replace('Z', '+00:00'))
                opportunity_date = dt.strftime('%Y-%m-%d')
            except:
                opportunity_date = publish_time
        else:
            opportunity_date = "غير محدد"
        
        # اسم الفرصة (Property Name)
        property_name = property_json.get('title', 'غير محدد')
        
        # المنطقة (Area/Location)
        location = property_json.get('location', 'غير محدد')
        
        # مساحة العقار (Property Size)
        property_size = extract_property_size(property_json)
        
        # قيمة الحصة (Share Price)
        down_payment = property_json.get('down_payment', 0)
        installment = property_json.get('installment', 0)
        currency = property_json.get('currency', 'EGP')
        
        # إجمالي قيمة العقار (Total Property Value)
        total_value = calculate_total_property_value(property_json)
        
        # Additional useful fields
        total_shares = property_json.get('total_shares', 0)
        available_shares = property_json.get('available_shares', 0)
        sold_shares = property_json.get('sold_shares', 0)
        property_type = property_json.get('property_type', 'غير محدد')
        property_sub_type = property_json.get('property_sub_type', 'غير محدد')
        funding_status = property_json.get('funding_status', 'غير محدد')
        delivery_date = property_json.get('delivery_date', 'غير محدد')
        exit_date = property_json.get('exit_date', 'غير محدد')
        
        properties_data.append({
            'property_id': property_id,
            'opportunity_date': opportunity_date,
            'property_name': property_name,
            'location': location,
            'property_size': property_size,
            'down_payment': down_payment,
            'installment': installment,
            'currency': currency,
            'total_value': total_value if total_value else 'محسوب من الأقساط',
            'total_shares': total_shares,
            'available_shares': available_shares,
            'sold_shares': sold_shares,
            'property_type': property_type,
            'property_sub_type': property_sub_type,
            'funding_status': funding_status,
            'delivery_date': delivery_date,
            'exit_date': exit_date
        })
    
    # Create CSV with Arabic headers
    csv_file = '_bmad-output/farida-properties-detailed.csv'
    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'property_id',
            'opportunity_date',
            'property_name',
            'location',
            'property_size',
            'down_payment',
            'installment',
            'currency',
            'total_value',
            'total_shares',
            'available_shares',
            'sold_shares',
            'property_type',
            'property_sub_type',
            'funding_status',
            'delivery_date',
            'exit_date'
        ])
        
        # Write Arabic headers
        writer.writerow({
            'property_id': 'رقم العقار',
            'opportunity_date': 'تاريخ الفرصة',
            'property_name': 'اسم الفرصة',
            'location': 'المنطقة',
            'property_size': 'مساحة العقار',
            'down_payment': 'الدفعة المقدمة',
            'installment': 'قيمة القسط',
            'currency': 'العملة',
            'total_value': 'إجمالي قيمة العقار',
            'total_shares': 'إجمالي الحصص',
            'available_shares': 'الحصص المتاحة',
            'sold_shares': 'الحصص المباعة',
            'property_type': 'نوع العقار',
            'property_sub_type': 'النوع الفرعي',
            'funding_status': 'حالة التمويل',
            'delivery_date': 'تاريخ التسليم',
            'exit_date': 'تاريخ الخروج'
        })
        
        # Write data
        writer.writerows(properties_data)
    
    print(f"\n✓ CSV file created: {csv_file}")
    print(f"✓ Total properties exported: {len(properties_data)}")
    
    # Create Arabic summary document
    md_file = '_bmad-output/farida-properties-arabic-summary.md'
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# تقرير تفصيلي عن فرص الاستثمار العقاري - فريدة إستيت\n\n")
        f.write(f"**تاريخ التقرير:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"**إجمالي الفرص المتاحة:** {len(properties_data)} فرصة استثمارية\n\n")
        f.write("---\n\n")
        
        # Summary statistics
        total_properties = len(properties_data)
        active_properties = sum(1 for p in properties_data if p['funding_status'] == 'available')
        total_shares_all = sum(p['total_shares'] for p in properties_data)
        available_shares_all = sum(p['available_shares'] for p in properties_data)
        sold_shares_all = sum(p['sold_shares'] for p in properties_data)
        
        f.write("## ملخص إحصائي\n\n")
        f.write(f"- **إجمالي الفرص:** {total_properties}\n")
        f.write(f"- **الفرص النشطة:** {active_properties}\n")
        f.write(f"- **إجمالي الحصص:** {total_shares_all}\n")
        f.write(f"- **الحصص المتاحة:** {available_shares_all}\n")
        f.write(f"- **الحصص المباعة:** {sold_shares_all}\n")
        if total_shares_all > 0:
            f.write(f"- **نسبة المبيعات:** {(sold_shares_all/total_shares_all*100):.1f}%\n\n")
        else:
            f.write(f"- **نسبة المبيعات:** 0.0%\n\n")
        
        f.write("---\n\n")
        f.write("## تفاصيل الفرص الاستثمارية\n\n")
        
        for i, prop in enumerate(properties_data, 1):
            f.write(f"### {i}. {prop['property_name']}\n\n")
            f.write(f"**رقم العقار:** {prop['property_id']}\n\n")
            f.write(f"**تاريخ الفرصة:** {prop['opportunity_date']}\n\n")
            f.write(f"**المنطقة:** {prop['location']}\n\n")
            f.write(f"**مساحة العقار:** {prop['property_size']}\n\n")
            f.write(f"**نوع العقار:** {prop['property_type']} - {prop['property_sub_type']}\n\n")
            
            f.write("#### التفاصيل المالية\n\n")
            f.write(f"- **الدفعة المقدمة:** {prop['down_payment']:,.0f} {prop['currency']}\n")
            f.write(f"- **قيمة القسط الشهري:** {prop['installment']:,.0f} {prop['currency']}\n")
            f.write(f"- **إجمالي قيمة الحصة:** {prop['total_value']}\n\n")
            
            f.write("#### معلومات الحصص\n\n")
            f.write(f"- **إجمالي الحصص:** {prop['total_shares']}\n")
            f.write(f"- **الحصص المتاحة:** {prop['available_shares']}\n")
            f.write(f"- **الحصص المباعة:** {prop['sold_shares']}\n")
            f.write(f"- **حالة التمويل:** {prop['funding_status']}\n\n")
            
            f.write("#### التواريخ المهمة\n\n")
            f.write(f"- **تاريخ التسليم:** {prop['delivery_date']}\n")
            f.write(f"- **تاريخ الخروج:** {prop['exit_date']}\n\n")
            
            f.write("---\n\n")
    
    print(f"✓ Arabic summary created: {md_file}")
    
    conn.close()
    print("\n✓ Report generation completed successfully!")

if __name__ == "__main__":
    main()
