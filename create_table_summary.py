#!/usr/bin/env python3
"""
Create table-formatted Arabic summary from property data
"""

import sqlite3
import json
from datetime import datetime

def main():
    conn = sqlite3.connect('data/farida.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT data_json FROM app_properties")
    rows = cursor.fetchall()
    
    all_properties = []
    
    for row in rows:
        try:
            data_json = json.loads(row[0])
            payload = data_json.get('payload', {})
            properties_array = payload.get('data', [])
            
            for prop in properties_array:
                property_id = prop.get('id', 'N/A')
                
                # Extract date
                publish_time = prop.get('publish_time', '')
                if publish_time:
                    try:
                        dt = datetime.fromisoformat(publish_time.replace('Z', '+00:00'))
                        opportunity_date = dt.strftime('%Y-%m-%d')
                    except:
                        opportunity_date = publish_time
                else:
                    opportunity_date = "غير محدد"
                
                property_name = prop.get('title', 'غير محدد')
                location = prop.get('location', 'غير محدد')
                property_type = prop.get('property_type', 'غير محدد')
                property_sub_type = prop.get('property_sub_type', 'غير محدد')
                
                # Financial details
                down_payment = prop.get('down_payment', 0)
                installment = prop.get('installment', 0)
                currency = prop.get('currency', 'EGP')
                
                # Calculate total
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
                
                # Shares info
                total_shares = prop.get('total_shares', 0)
                available_shares = prop.get('available_shares', 0)
                sold_shares = prop.get('sold_shares', 0)
                funding_status = prop.get('funding_status', 'غير محدد')
                
                # Dates
                delivery_date = prop.get('delivery_date', 'غير محدد')
                exit_date = prop.get('exit_date', 'غير محدد')
                installments_count = prop.get('installments_count', 0)
                
                all_properties.append({
                    'id': property_id,
                    'date': opportunity_date,
                    'name': property_name,
                    'location': location,
                    'type': f"{property_type} - {property_sub_type}",
                    'down': f"{down_payment:,.0f}",
                    'installment': f"{installment:,.0f}",
                    'installments_count': installments_count,
                    'total': f"{total_value:,.0f}",
                    'currency': currency,
                    'total_shares': total_shares,
                    'available': available_shares,
                    'sold': sold_shares,
                    'status': funding_status,
                    'delivery': delivery_date,
                    'exit': exit_date
                })
        
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    # Create markdown with tables
    md_file = '_bmad-output/farida-properties-arabic-summary.md'
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# تقرير تفصيلي عن فرص الاستثمار العقاري - فريدة إستيت\n\n")
        f.write(f"**تاريخ التقرير:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"**إجمالي الفرص المتاحة:** {len(all_properties)} فرصة استثمارية\n\n")
        f.write("---\n\n")
        
        # Statistics
        active = sum(1 for p in all_properties if p['status'] == 'available')
        funded = sum(1 for p in all_properties if p['status'] == 'funded')
        total_shares_all = sum(p['total_shares'] for p in all_properties)
        available_shares_all = sum(p['available'] for p in all_properties)
        sold_shares_all = sum(p['sold'] for p in all_properties)
        
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
        f.write("## جدول الفرص الاستثمارية الكامل\n\n")
        
        # Main properties table
        f.write("| # | رقم العقار | تاريخ الفرصة | اسم الفرصة | المنطقة | نوع العقار |\n")
        f.write("|---|-----------|-------------|-----------|---------|----------|\n")
        
        for i, prop in enumerate(all_properties, 1):
            f.write(f"| {i} | {prop['id']} | {prop['date']} | {prop['name']} | {prop['location']} | {prop['type']} |\n")
        
        f.write("\n---\n\n")
        f.write("## التفاصيل المالية\n\n")
        
        # Financial details table
        f.write("| # | اسم الفرصة | الدفعة المقدمة | القسط الشهري | عدد الأقساط | إجمالي القيمة | العملة |\n")
        f.write("|---|-----------|----------------|-------------|------------|--------------|-------|\n")
        
        for i, prop in enumerate(all_properties, 1):
            f.write(f"| {i} | {prop['name']} | {prop['down']} | {prop['installment']} | {prop['installments_count']} | {prop['total']} | {prop['currency']} |\n")
        
        f.write("\n---\n\n")
        f.write("## معلومات الحصص والتمويل\n\n")
        
        # Shares table
        f.write("| # | اسم الفرصة | إجمالي الحصص | الحصص المتاحة | الحصص المباعة | حالة التمويل |\n")
        f.write("|---|-----------|--------------|---------------|--------------|-------------|\n")
        
        for i, prop in enumerate(all_properties, 1):
            f.write(f"| {i} | {prop['name']} | {prop['total_shares']} | {prop['available']} | {prop['sold']} | {prop['status']} |\n")
        
        f.write("\n---\n\n")
        f.write("## التواريخ المهمة\n\n")
        
        # Dates table
        f.write("| # | اسم الفرصة | تاريخ التسليم | تاريخ الخروج |\n")
        f.write("|---|-----------|--------------|-------------|\n")
        
        for i, prop in enumerate(all_properties, 1):
            f.write(f"| {i} | {prop['name']} | {prop['delivery']} | {prop['exit']} |\n")
        
        f.write("\n---\n\n")
        f.write("## ملاحظات\n\n")
        f.write("- **مساحة العقار:** غير متوفرة في بيانات API\n")
        f.write("- **العملة:** جميع القيم بالجنيه المصري (EGP) ما لم يُذكر خلاف ذلك\n")
        f.write("- **البيانات:** مستخرجة من قاعدة البيانات بتاريخ التقرير\n")
        f.write(f"- **المصدر:** app.farida.estate API\n")
    
    print(f"✅ Table-formatted summary created: {md_file}")
    conn.close()

if __name__ == "__main__":
    main()
