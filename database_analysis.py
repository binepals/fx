# database_analysis.py
# Quick analysis of current Exchange Rate database to plan extensions

import sqlite3
import pandas as pd
from datetime import datetime, date

def analyze_current_data():
    """Analyze current database to understand scope for extensions"""
    
    print("🔍 CURRENT DATABASE ANALYSIS")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect('fx_rates.db')
        
        # Overall statistics
        print("\n📊 OVERALL STATISTICS")
        print("-" * 30)
        
        overall_query = """
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT date) as unique_dates,
                COUNT(DISTINCT target_currency) as unique_currencies,
                MIN(date) as earliest_date,
                MAX(date) as latest_date
            FROM exchange_rates
        """
        
        overall_df = pd.read_sql_query(overall_query, conn)
        
        for _, row in overall_df.iterrows():
            print(f"📋 Total Records: {row['total_records']:,}")
            print(f"📅 Date Range: {row['earliest_date']} to {row['latest_date']}")
            print(f"📆 Unique Days: {row['unique_dates']}")
            print(f"💱 Currencies: {row['unique_currencies']}")
        
        # Currency breakdown
        print("\n💱 CURRENCY BREAKDOWN")
        print("-" * 30)
        
        currency_query = """
            SELECT 
                target_currency,
                COUNT(*) as record_count,
                MIN(date) as first_date,
                MAX(date) as last_date,
                COUNT(DISTINCT date) as days_covered
            FROM exchange_rates
            GROUP BY target_currency
            ORDER BY record_count DESC
        """
        
        currency_df = pd.read_sql_query(currency_query, conn)
        print(currency_df.to_string(index=False))
        
        # Monthly coverage
        print("\n📅 MONTHLY COVERAGE")
        print("-" * 30)
        
        monthly_query = """
            SELECT 
                strftime('%Y-%m', date) as year_month,
                COUNT(DISTINCT target_currency) as currencies_count,
                COUNT(*) as total_records
            FROM exchange_rates
            GROUP BY strftime('%Y-%m', date)
            ORDER BY year_month DESC
        """
        
        monthly_df = pd.read_sql_query(monthly_query, conn)
        print(monthly_df.head(12).to_string(index=False))  # Show last 12 months
        
        # Application currencies status
        print("\n⚙️ APPLICATION CURRENCIES STATUS")
        print("-" * 30)
        
        app_currency_query = """
            SELECT 
                ac.currency_code,
                ac.currency_name,
                ac.is_active,
                COALESCE(er.record_count, 0) as data_records,
                er.first_date,
                er.last_date
            FROM application_currencies ac
            LEFT JOIN (
                SELECT 
                    target_currency,
                    COUNT(*) as record_count,
                    MIN(date) as first_date,
                    MAX(date) as last_date
                FROM exchange_rates
                GROUP BY target_currency
            ) er ON ac.currency_code = er.target_currency
            ORDER BY ac.currency_code
        """
        
        app_df = pd.read_sql_query(app_currency_query, conn)
        print(app_df.to_string(index=False))
        
        # Data gaps analysis
        print("\n⚠️  DATA GAPS ANALYSIS")
        print("-" * 30)
        
        # Find currencies in app list but missing data
        missing_data = app_df[app_df['data_records'] == 0]
        if len(missing_data) > 0:
            print("❌ Currencies configured but missing data:")
            for _, row in missing_data.iterrows():
                status = "ACTIVE" if row['is_active'] else "INACTIVE"
                print(f"   • {row['currency_code']} ({row['currency_name']}) - {status}")
        else:
            print("✅ All configured currencies have data")
        
        # Check for potential new currencies from ECB
        print("\n🆕 EXPANSION OPPORTUNITIES")
        print("-" * 30)
        
        # ECB has many more currencies available
        ecb_major_currencies = [
            'USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NOK', 'DKK',
            'PLN', 'CZK', 'HUF', 'RON', 'BGN', 'HRK', 'RUB', 'TRY', 'BRL', 'MXN',
            'SGD', 'HKD', 'KRW', 'INR', 'IDR', 'PHP', 'MYR', 'THB', 'NZD', 'ILS',
            'CLP', 'PEN', 'COP', 'ARS', 'UYU'
        ]
        
        current_currencies = set(currency_df['target_currency'].tolist())
        available_new = [curr for curr in ecb_major_currencies if curr not in current_currencies and curr != 'GBP']
        
        print(f"📈 Available for addition: {len(available_new)} currencies")
        print(f"💡 Examples: {', '.join(available_new[:10])}")
        if len(available_new) > 10:
            print(f"   + {len(available_new) - 10} more...")
        
        # Date range extension opportunities
        print("\n📅 DATE RANGE EXTENSION")
        print("-" * 30)
        
        current_start = overall_df['earliest_date'].iloc[0]
        current_end = overall_df['latest_date'].iloc[0]
        
        print(f"📊 Current range: {current_start} to {current_end}")
        print(f"💡 ECB data available from: 1999-01-04 (Euro introduction)")
        print(f"🎯 Suggested extensions:")
        print(f"   • Historical: 2022-01-01 to {current_start} (adds ~1.5 years)")
        print(f"   • Recent: {current_end} to today (if behind)")
        
        conn.close()
        
        return {
            'total_records': overall_df['total_records'].iloc[0],
            'currencies': currency_df['target_currency'].tolist(),
            'date_range': (current_start, current_end),
            'available_new_currencies': available_new[:20],  # Top 20 for extension
            'missing_app_currencies': missing_data['currency_code'].tolist() if len(missing_data) > 0 else []
        }
        
    except Exception as e:
        print(f"❌ Error analyzing database: {str(e)}")
        return None

def recommend_next_steps(analysis_data):
    """Provide specific recommendations based on analysis"""
    
    if not analysis_data:
        return
    
    print(f"\n🎯 RECOMMENDED NEXT STEPS")
    print("=" * 50)
    
    print("1️⃣  **IMMEDIATE PRIORITY - Extend Currency Coverage**")
    print("   Add these high-value currencies:")
    priority_currencies = ['NOK', 'DKK', 'PLN', 'CZK', 'SGD', 'HKD', 'KRW', 'INR', 'NZD', 'ILS']
    available_priority = [c for c in priority_currencies if c in analysis_data['available_new_currencies']]
    print(f"   💰 {', '.join(available_priority[:5])}")
    
    print("\n2️⃣  **EXTEND HISTORICAL DATA**")
    print("   📈 Add data from 2022-01-01 (approximately 500+ additional days)")
    print("   🎯 This gives 3+ years of data for trend analysis")
    
    print("\n3️⃣  **ENHANCE APPLICATION CURRENCIES**")
    if analysis_data['missing_app_currencies']:
        print(f"   ⚠️  Fix missing data for: {', '.join(analysis_data['missing_app_currencies'])}")
    print("   ✅ Add priority currencies to application list")
    
    print("\n4️⃣  **ADD ANALYTICS FEATURES**")
    print("   📊 Volatility analysis (30-day rolling)")
    print("   📈 Trend analysis (3-month, 6-month, 1-year)")
    print("   🔍 Correlation analysis between currencies")
    
    print(f"\n📋 **IMPLEMENTATION ORDER:**")
    print(f"   Week 1: Extend ECB importer for more currencies + historical data")
    print(f"   Week 2: Add volatility and trend calculations")
    print(f"   Week 3: Enhanced dashboard with trend visualizations")
    print(f"   Week 4: Correlation analysis and forecasting basics")

if __name__ == "__main__":
    analysis_data = analyze_current_data()
    recommend_next_steps(analysis_data)