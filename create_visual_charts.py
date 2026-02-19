#!/usr/bin/env python3
"""
Create visual charts and graphs for Farida Estate data
Generates PNG images and an updated markdown report with embedded charts
"""

import sqlite3
import json
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import os

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 10

# Create output directory for charts
os.makedirs('_bmad-output/charts', exist_ok=True)

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
                    'title': prop.get('title', 'Unknown'),
                    'location': prop.get('location', 'Unknown'),
                    'property_type': prop.get('property_type', 'Unknown'),
                    'total_shares': prop.get('total_shares', 0),
                    'available_shares': prop.get('available_shares', 0),
                    'sold_shares': prop.get('sold_shares', 0),
                    'funding_status': prop.get('funding_status', 'unknown'),
                    'total_value': total_value,
                    'down_payment': prop.get('down_payment', 0),
                    'installment': prop.get('installment', 0),
                    'exit_date': prop.get('exit_date', 'Unknown')
                })
        except Exception as e:
            print(f"Error processing property: {e}")
            continue
    
    conn.close()
    return properties

def create_funding_status_chart(properties):
    """Chart 1: Funding Status Distribution"""
    status_counts = {}
    for prop in properties:
        status = prop['funding_status']
        status_counts[status] = status_counts.get(status, 0) + 1
    
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ['#2ecc71', '#e74c3c', '#95a5a6']
    
    statuses = list(status_counts.keys())
    counts = list(status_counts.values())
    
    bars = ax.bar(statuses, counts, color=colors[:len(statuses)])
    ax.set_xlabel('Funding Status', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of Properties', fontsize=12, fontweight='bold')
    ax.set_title('Property Funding Status Distribution', fontsize=14, fontweight='bold')
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('_bmad-output/charts/funding_status.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: funding_status.png")

def create_shares_availability_chart(properties):
    """Chart 2: Shares Availability"""
    total_shares = sum(p['total_shares'] for p in properties)
    available_shares = sum(p['available_shares'] for p in properties)
    sold_shares = sum(p['sold_shares'] for p in properties)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    categories = ['Total Shares', 'Available Shares', 'Sold Shares']
    values = [total_shares, available_shares, sold_shares]
    colors = ['#3498db', '#2ecc71', '#e74c3c']
    
    bars = ax.bar(categories, values, color=colors)
    ax.set_ylabel('Number of Shares', fontsize=12, fontweight='bold')
    ax.set_title('Market Shares Overview', fontsize=14, fontweight='bold')
    
    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontweight='bold', fontsize=11)
    
    # Add percentage sold
    pct_sold = (sold_shares / total_shares * 100) if total_shares > 0 else 0
    ax.text(0.5, 0.95, f'Sales Rate: {pct_sold:.1f}%',
            transform=ax.transAxes, ha='center', va='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
            fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('_bmad-output/charts/shares_availability.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: shares_availability.png")

def create_property_type_distribution(properties):
    """Chart 3: Property Type Distribution"""
    type_counts = {}
    for prop in properties:
        ptype = prop['property_type']
        type_counts[ptype] = type_counts.get(ptype, 0) + 1
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    types = list(type_counts.keys())
    counts = list(type_counts.values())
    colors = sns.color_palette("husl", len(types))
    
    wedges, texts, autotexts = ax.pie(counts, labels=types, autopct='%1.1f%%',
                                        colors=colors, startangle=90)
    
    # Make percentage text bold
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(10)
    
    ax.set_title('Property Type Distribution', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('_bmad-output/charts/property_types.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: property_types.png")

def create_investment_value_distribution(properties):
    """Chart 4: Investment Value Distribution"""
    values = [p['total_value'] for p in properties if p['total_value'] > 0]
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    ax.hist(values, bins=15, color='#3498db', edgecolor='black', alpha=0.7)
    ax.set_xlabel('Total Investment Value (EGP)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of Properties', fontsize=12, fontweight='bold')
    ax.set_title('Investment Value Distribution', fontsize=14, fontweight='bold')
    
    # Add statistics
    avg_value = sum(values) / len(values) if values else 0
    ax.axvline(avg_value, color='red', linestyle='--', linewidth=2, label=f'Average: {avg_value:,.0f} EGP')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig('_bmad-output/charts/value_distribution.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: value_distribution.png")

def create_top_properties_chart(properties):
    """Chart 5: Top 10 Properties by Total Value"""
    # Sort by total value
    sorted_props = sorted(properties, key=lambda x: x['total_value'], reverse=True)[:10]
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    titles = [p['title'][:30] + '...' if len(p['title']) > 30 else p['title'] for p in sorted_props]
    values = [p['total_value'] for p in sorted_props]
    
    bars = ax.barh(titles, values, color='#e74c3c')
    ax.set_xlabel('Total Value (EGP)', fontsize=12, fontweight='bold')
    ax.set_title('Top 10 Properties by Investment Value', fontsize=14, fontweight='bold')
    
    # Add value labels
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height()/2.,
                f'{width:,.0f}',
                ha='left', va='center', fontweight='bold', fontsize=9)
    
    plt.tight_layout()
    plt.savefig('_bmad-output/charts/top_properties.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: top_properties.png")

def create_availability_heatmap(properties):
    """Chart 6: Share Availability Heatmap"""
    # Calculate availability percentage for each property
    availability_data = []
    for prop in properties[:20]:  # Top 20 properties
        if prop['total_shares'] > 0:
            pct_available = (prop['available_shares'] / prop['total_shares']) * 100
            availability_data.append({
                'title': prop['title'][:25] + '...' if len(prop['title']) > 25 else prop['title'],
                'available_pct': pct_available,
                'status': prop['funding_status']
            })
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    titles = [d['title'] for d in availability_data]
    percentages = [d['available_pct'] for d in availability_data]
    colors_map = ['#2ecc71' if d['status'] == 'available' else '#e74c3c' for d in availability_data]
    
    bars = ax.barh(titles, percentages, color=colors_map)
    ax.set_xlabel('Available Shares (%)', fontsize=12, fontweight='bold')
    ax.set_title('Share Availability by Property (Top 20)', fontsize=14, fontweight='bold')
    ax.set_xlim(0, 100)
    
    # Add percentage labels
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width + 2, bar.get_y() + bar.get_height()/2.,
                f'{width:.0f}%',
                ha='left', va='center', fontweight='bold', fontsize=8)
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor='#2ecc71', label='Available'),
                      Patch(facecolor='#e74c3c', label='Funded')]
    ax.legend(handles=legend_elements, loc='lower right')
    
    plt.tight_layout()
    plt.savefig('_bmad-output/charts/availability_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: availability_heatmap.png")

def create_markdown_report(properties):
    """Create updated markdown with embedded charts"""
    md_file = '_bmad-output/farida-estate-visual-summary.md'
    
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# Farida Estate Investment Platform - Visual Analytics Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Total Properties Analyzed:** {len(properties)}\n\n")
        f.write("---\n\n")
        
        # Statistics
        total_shares = sum(p['total_shares'] for p in properties)
        available_shares = sum(p['available_shares'] for p in properties)
        sold_shares = sum(p['sold_shares'] for p in properties)
        sales_rate = (sold_shares / total_shares * 100) if total_shares > 0 else 0
        
        f.write("## 📊 Key Metrics\n\n")
        f.write(f"- **Total Properties:** {len(properties)}\n")
        f.write(f"- **Total Shares:** {total_shares:,}\n")
        f.write(f"- **Available Shares:** {available_shares:,}\n")
        f.write(f"- **Sold Shares:** {sold_shares:,}\n")
        f.write(f"- **Sales Rate:** {sales_rate:.1f}%\n\n")
        
        f.write("---\n\n")
        
        # Chart 1
        f.write("## 1. Funding Status Distribution\n\n")
        f.write("![Funding Status](charts/funding_status.png)\n\n")
        f.write("This chart shows the distribution of properties by their funding status.\n\n")
        f.write("---\n\n")
        
        # Chart 2
        f.write("## 2. Market Shares Overview\n\n")
        f.write("![Shares Availability](charts/shares_availability.png)\n\n")
        f.write("Overview of total, available, and sold shares across all properties.\n\n")
        f.write("---\n\n")
        
        # Chart 3
        f.write("## 3. Property Type Distribution\n\n")
        f.write("![Property Types](charts/property_types.png)\n\n")
        f.write("Breakdown of properties by type (residential, commercial, administrative, etc.).\n\n")
        f.write("---\n\n")
        
        # Chart 4
        f.write("## 4. Investment Value Distribution\n\n")
        f.write("![Value Distribution](charts/value_distribution.png)\n\n")
        f.write("Distribution of investment values across all properties.\n\n")
        f.write("---\n\n")
        
        # Chart 5
        f.write("## 5. Top 10 Properties by Value\n\n")
        f.write("![Top Properties](charts/top_properties.png)\n\n")
        f.write("The highest-value investment opportunities currently available.\n\n")
        f.write("---\n\n")
        
        # Chart 6
        f.write("## 6. Share Availability Heatmap\n\n")
        f.write("![Availability Heatmap](charts/availability_heatmap.png)\n\n")
        f.write("Visual representation of share availability across top 20 properties.\n\n")
        f.write("---\n\n")
        
        f.write("## 📈 Investment Insights\n\n")
        
        # Calculate insights
        available_props = sum(1 for p in properties if p['funding_status'] == 'available')
        funded_props = sum(1 for p in properties if p['funding_status'] == 'funded')
        
        f.write(f"- **Available Opportunities:** {available_props} properties ({available_props/len(properties)*100:.1f}%)\n")
        f.write(f"- **Fully Funded:** {funded_props} properties ({funded_props/len(properties)*100:.1f}%)\n")
        
        avg_value = sum(p['total_value'] for p in properties) / len(properties) if properties else 0
        f.write(f"- **Average Investment Value:** {avg_value:,.0f} EGP\n\n")
        
        f.write("---\n\n")
        f.write("**Report Generated by:** BMad Master Analytics Engine\n")
        f.write("**Data Source:** Farida Estate SQLite Database\n")
        f.write("**Visualization Library:** Matplotlib + Seaborn\n")
    
    print(f"✓ Created: {md_file}")

def main():
    print("🎨 Generating visual charts for Farida Estate data...\n")
    
    # Get data
    properties = get_property_data()
    print(f"📊 Loaded {len(properties)} properties from database\n")
    
    # Create charts
    print("Creating charts...")
    create_funding_status_chart(properties)
    create_shares_availability_chart(properties)
    create_property_type_distribution(properties)
    create_investment_value_distribution(properties)
    create_top_properties_chart(properties)
    create_availability_heatmap(properties)
    
    print("\nCreating markdown report...")
    create_markdown_report(properties)
    
    print("\n✅ All visualizations created successfully!")
    print("\nGenerated files:")
    print("  📁 _bmad-output/charts/ (6 PNG images)")
    print("  📄 _bmad-output/farida-estate-visual-summary.md (updated report)")

if __name__ == "__main__":
    main()
