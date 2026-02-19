"""Analyze scraped data from Farida Estate database."""

import sqlite3
import json
from datetime import datetime

def analyze_database():
    conn = sqlite3.connect('data/farida.db')
    
    print("=" * 80)
    print("FARIDA ESTATE SCRAPING PIPELINE - DATA ANALYSIS REPORT")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Database Overview
    print("=" * 80)
    print("DATABASE OVERVIEW")
    print("=" * 80)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    
    for table in tables:
        if not table[0].startswith('sqlite_'):
            count = conn.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
            print(f"  {table[0]:30} {count:5} rows")
    
    # Investor Profile Analysis
    print("\n" + "=" * 80)
    print("INVESTOR PROFILE")
    print("=" * 80)
    profile_data = conn.execute(
        'SELECT data_json FROM app_investor_profile ORDER BY scraped_at DESC LIMIT 1'
    ).fetchone()
    
    if profile_data:
        profile = json.loads(profile_data[0])
        data = profile.get('payload', {}).get('data', {})
        print(f"  Name: {data.get('name')}")
        print(f"  Email: {data.get('email')}")
        print(f"  Phone: {data.get('phone')}")
        print(f"  Country: {data.get('country')}")
        print(f"  Referral Code: {data.get('referral_code')}")
        print(f"  Email Verified: {data.get('is_email_verified')}")
        print(f"  National ID Status: {data.get('national_id_status')}")
        print(f"  UK KYC Status: {data.get('uk_kyc_status')}")
        
        referred_by = data.get('referred_by', {})
        if referred_by:
            print(f"\n  Referred By:")
            print(f"    Name: {referred_by.get('name')}")
            print(f"    Email: {referred_by.get('email')}")
            print(f"    Referral Code: {referred_by.get('referral_code')}")
    
    # Wallet Analysis
    print("\n" + "=" * 80)
    print("WALLET BALANCE")
    print("=" * 80)
    wallet_data = conn.execute(
        'SELECT data_json FROM app_wallet_balance ORDER BY scraped_at DESC LIMIT 1'
    ).fetchone()
    
    if wallet_data:
        wallet = json.loads(wallet_data[0])
        balances = wallet.get('payload', {}).get('data', [])
        for balance in balances:
            print(f"  {balance.get('currency')}:")
            print(f"    Total Amount: {balance.get('amount'):,.2f}")
            print(f"    Withdrawable: {balance.get('withdrawable_amount'):,.2f}")
            print(f"    Non-Withdrawable: {balance.get('non_withdrawable_amount'):,.2f}")
    
    # Portfolio Analysis
    print("\n" + "=" * 80)
    print("PORTFOLIO SUMMARY")
    print("=" * 80)
    portfolio_data = conn.execute(
        'SELECT data_json FROM app_portfolio ORDER BY scraped_at DESC LIMIT 1'
    ).fetchone()
    
    if portfolio_data:
        portfolio = json.loads(portfolio_data[0])
        pdata = portfolio.get('payload', {}).get('data', {})
        print(f"  Total Properties Owned: {pdata.get('total_properties', 0)}")
        print(f"  Total Investment: {pdata.get('total_investment', 0):,.2f}")
        print(f"  Total Current Value: {pdata.get('total_value', 0):,.2f}")
        print(f"  Total Returns: {pdata.get('total_returns', 0):,.2f}")
    
    # Properties Market Analysis
    print("\n" + "=" * 80)
    print("PROPERTIES MARKET OVERVIEW")
    print("=" * 80)
    props_data = conn.execute(
        'SELECT data_json FROM app_properties ORDER BY scraped_at DESC LIMIT 1'
    ).fetchone()
    
    if props_data:
        properties = json.loads(props_data[0])
        pagination = properties.get('payload', {}).get('pagination', {})
        props_list = properties.get('payload', {}).get('data', [])
        
        print(f"  Total Properties Available: {pagination.get('total', 0)}")
        print(f"  Properties per Page: {pagination.get('per_page', 0)}")
        print(f"  Current Page: {pagination.get('current_page', 0)}")
        
        if props_list:
            print(f"\n  Sample Properties (First 5):")
            for i, prop in enumerate(props_list[:5], 1):
                print(f"\n  Property {i}:")
                print(f"    ID: {prop.get('id')}")
                print(f"    Currency: {prop.get('currency')}")
                print(f"    Available Shares: {prop.get('available_shares')}")
                print(f"    Max Shares/Investor: {prop.get('max_shares_per_investor')}")
                print(f"    Delivery Date: {prop.get('delivery_date')}")
                print(f"    Exit Date: {prop.get('exit_date')}")
                print(f"    Waiting List: {'Yes' if prop.get('accept_waiting_list') else 'No'}")
    
    # Scrape History
    print("\n" + "=" * 80)
    print("SCRAPE HISTORY (Last 10 Runs)")
    print("=" * 80)
    runs = conn.execute('''
        SELECT layer, endpoint, started_at, items_scraped, errors, status
        FROM scrape_runs 
        ORDER BY started_at DESC 
        LIMIT 10
    ''').fetchall()
    
    print(f"  {'Layer':<8} {'Endpoint':<25} {'Started':<20} {'Items':<6} {'Errors':<7} {'Status'}")
    print("  " + "-" * 76)
    for r in runs:
        print(f"  {r[0]:<8} {r[1]:<25} {r[2][:19]:<20} {r[3]:<6} {r[4]:<7} {r[5] or 'success'}")
    
    # WordPress Content Analysis
    print("\n" + "=" * 80)
    print("WORDPRESS CONTENT SUMMARY")
    print("=" * 80)
    
    posts_count = conn.execute("SELECT COUNT(*) FROM wp_posts").fetchone()[0]
    pages_count = conn.execute("SELECT COUNT(*) FROM wp_pages").fetchone()[0]
    media_count = conn.execute("SELECT COUNT(*) FROM wp_media").fetchone()[0]
    categories_count = conn.execute("SELECT COUNT(*) FROM wp_categories").fetchone()[0]
    
    print(f"  Posts: {posts_count}")
    print(f"  Pages: {pages_count}")
    print(f"  Media Items: {media_count}")
    print(f"  Categories: {categories_count}")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("END OF REPORT")
    print("=" * 80)


if __name__ == "__main__":
    analyze_database()
