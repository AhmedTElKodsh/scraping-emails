"""Extract detailed property information from Farida Estate database."""

import sqlite3
import json
import csv
from datetime import datetime

def extract_property_details():
    conn = sqlite3.connect('data/farida.db')
    
    props_data = conn.execute(
        'SELECT data_json FROM app_properties ORDER BY scraped_at DESC LIMIT 1'
    ).fetchone()
    
    if not props_data:
        print("No property data found!")
        return
    
    properties = json.loads(props_data[0])
    props_list = properties.get('payload', {}).get('data', [])
    
    print("=" * 120)
    print("FARIDA ESTATE - DETAILED PROPERTY ANALYSIS")
    print("=" * 120)
    print(f"Total Properties: {len(props_list)}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    csv_data = []
    
    for i, prop in enumerate(props_list, 1):
        print(f"\n{'='*120}")
        print(f"PROPERTY #{i} - ID: {prop.get('id')}")
        print(f"{'='*120}")
        
        details = {}
        for key, value in prop.items():
            if isinstance(value, (dict, list)):
                details[key] = json.dumps(value, ensure_ascii=False)
            else:
                details[key] = value
        
        print(json.dumps(prop, indent=2, ensure_ascii=False))
        csv_data.append(details)
    
    if csv_data:
        csv_filename = '_bmad-output/farida-properties-detailed.csv'
        with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = csv_data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_data)
        
        print(f"\n\n{'='*120}")
        print(f"CSV Export Complete: {csv_filename}")
        print(f"{'='*120}")
    
    conn.close()

if __name__ == "__main__":
    extract_property_details()
