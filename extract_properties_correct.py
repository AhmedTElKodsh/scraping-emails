#!/usr/bin/env python3
"""
Extract property data from correct JSON structure in database
The data is nested: data_json -> payload -> data[]
"""

import sqlite3
import json
import csv
from datetime import datetime

def main():
    conn = sqlite3.connect('data/farida.db')
    cursor = conn.cursor()
    
    # Get all property records
    cursor.execute("SELECT data_json FROM app_properties")
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} property records in database")
    
    all_properties = []
    
    for row in rows:
        try:
            # Parse the outer JSON
            data_json = json.loads(row[0])
            
            # Navigate to the properties array
            payload = data_json.get('payload', {})
            properties_array = payload.get('data', [])
            
            print(f"Extracted {len(properties_array)} properties from this record")
            
            # Process each property
            for prop in properties_array:
                # Extract required fields
                property_id = prop.get('id', 'N/A')
                
                # تاريخ الفرصة (Opportunity Date)
                publish_time = prop.get('publish_time', '')
                if publish_time:
                    try:
                        dt = datetime.fromisoformat(publish_time.replace('Z', '+00:00'))
                        opportunity_date = dt.strftime('%Y-%m-%d')
                    except:
                        opportunity_date = publish_time
                else:
                    opportunity_date = "غير محدد"
                
                # اسم الفرصة (Property Name)
                property_name = prop.get('title', 'غير محدد')
                
                # المنطقة (Location)
                location = prop.get('location', 'غير محدد')
                
                # مساحة العقار (Property Size) - not in data, mark as N/A
                property_size = "غير متوفر في البيانات"
                
                # قيمة الحصة (Share Price components)
                down_payment = prop.get('down_payment', 0)
                installment = prop.get('installment', 0)
                currency = prop.get('currency', 'EGP')
                
                # Calculate total from payment schedules
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
                
                # Additional fields
                total_shares = prop.get('total_shares', 0)
                available_shares = prop.get('available_shares', 0)
                sold_shares = prop.get('sold_shares', 0)
                property_type = prop.get('property_type', 'غير محدد')
                property_sub_type = prop.get('property_sub_type', 'غير محدد')
                funding_status = prop.get('funding_status', 'غير محدد')
                delivery_date = prop.get('delivery_date', 'غير محدد')
                exit_date = prop.get('exit_date', 'غير محدد')
                installments_count = prop.get('installments_count', 0)
                
                all_properties.append({
                    'property_id': property_id,
                    'opportunity_date': opportunity_date,
                    'property_name': property_name,
                    'location': location,
                    'property_size': property_size,
                    'down_payment': down_payment,
                    'installment': installment,
                    'currency': currency,
                    'total_value': f"{total_value:,.0f}" if total_value > 0 else "0",
                    'total_shares': total_shares,
                    'available_shares': available_shares,
                    'sold_shares': sold_shares,
                    'property_type': property_type,
                    'property_sub_type': property_sub_type,
                    'funding_status': funding_status,
                    'delivery_date': delivery_date,
                    'exit_date': exit_date,
                    'installments_count': installments_count
                })
        
        except Exception as e:
            print(f"Error processing record: {e}")
            continue
    
    print(f"\nTotal properties extracted: {len(all_properties)}")
    
    # Create CSV
    csv_file = '_bmad-output/farida-properties-detailed.csv'
    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'property_id', 'opportunity_date', 'property_name', 'location',
            'property_size', 'down_payment', 'installment', 'currency',
            'total_value', 'total_shares', 'available_shares', 'sold_shares',
            'property_type', 'property_sub_type', 'funding_status',
            'delivery_date', 'exit_date', 'installments_count'
        ])
        
        # Arabic headers
        writer.writerow({
            'property_id': 'رقم العقار',
            'opportunity_date': 'تاريخ الفرصة',
            'property_name': 'اسم الفرصة',
            'location': 'المنطقة',
            'property_size': 'مساحة العقار',
            'down_payment': 'الدفعة المقدمة',
            'installment': 'قيمة القسط',
            'currency': 'العملة',
            'total_value': 'إجمالي قيمة الحصة',
            'total_shares': 'إجمالي الحصص',
            'available_shares': 'الحصص المتاحة',
            'sold_shares': 'الحصص المباعة',
            'property_type': 'نوع العقار',
            'property_sub_type': 'النوع الفرعي',
            'funding_status': 'حالة التمويل',
            'delivery_date': 'تاريخ التسليم',
            'exit_date': 'تاريخ الخروج',
            'installments_count': 'عدد الأقساط'
        })
        
        writer.writerows(all_properties)
    
    print(f"✓ CSV created: {csv_file}")
    
    # Create Arabic summary
    md_file = '_bmad-output/farida-properties-arabic-summary.md'
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# تقرير تفصيلي عن فرص الاستثمار العقاري - فريدة إستيت\n\n")
        f.write(f"**تاريخ التقرير:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"**إجمالي الفرص المتاحة:** {len(all_properties)} فرصة استثمارية\n\n")
        f.write("---\n\n")
        
        # Statistics
        active = sum(1 for p in all_properties if p['funding_status'] == 'available')
        funded = sum(1 for p in all_properties if p['funding_status'] == 'funded')
        total_shares_all = sum(p['total_shares'] for p in all_properties)
        available_shares_all = sum(p['available_shares'] for p in all_properties)
        sold_shares_all = sum(p['sold_shares'] for p in all_properties)
        
        f.write("## ملخص إحصائي\n\n")
        f.write(f"- **إجمالي الفرص:** {len(all_properties)}\n")
        f.write(f"- **الفرص المتاحة:** {active}\n")
        f.write(f"- **الفرص الممولة بالكامل:** {funded}\n")
        f.write(f"- **إجمالي الحصص:** {total_shares_all}\n")
        f.write(f"- **الحصص المتاحة:** {available_shares_all}\n")
        f.write(f"- **الحصص المباعة:** {sold_shares_all}\n")
        if total_shares_all > 0:
            f.write(f"- **نسبة المبيعات:** {(sold_shares_all/total_shares_all*100):.1f}%\n\n")
        
        f.write("---\n\n")
        f.write("## تفاصيل الفرص الاستثمارية\n\n")
        
        for i, prop in enumerate(all_properties, 1):
            f.write(f"### {i}. {prop['property_name']}\n\n")
            f.write(f"**رقم العقار:** {prop['property_id']}\n\n")
            f.write(f"**تاريخ الفرصة:** {prop['opportunity_date']}\n\n")
            f.write(f"**المنطقة:** {prop['location']}\n\n")
            f.write(f"**مساحة العقار:** {prop['property_size']}\n\n")
            f.write(f"**نوع العقار:** {prop['property_type']} - {prop['property_sub_type']}\n\n")
            
            f.write("#### التفاصيل المالية\n\n")
            f.write(f"- **الدفعة المقدمة:** {prop['down_payment']:,.0f} {prop['currency']}\n")
            f.write(f"- **قيمة القسط الشهري:** {prop['installment']:,.0f} {prop['currency']}\n")
            f.write(f"- **عدد الأقساط:** {prop['installments_count']}\n")
            f.write(f"- **إجمالي قيمة الحصة:** {prop['total_value']} {prop['currency']}\n\n")
            
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
    print("\n✅ Report generation completed successfully!")
    print(f"\nFiles created:")
    print(f"  1. {csv_file} - Excel-compatible CSV with Arabic headers")
    print(f"  2. {md_file} - Detailed Arabic summary document")

if __name__ == "__main__":
    main()
