import pandas as pd
import numpy as np
import requests
import sqlite3
import io
from datetime import datetime, date, timedelta
import time
import zipfile

def download_ecb_csv_data():
    """
    Download ECB historical exchange rate CSV data directly
    """
    
    print("📊 Downloading ECB Reference Rates")
    print("=" * 50)
    
    # ECB publishes daily reference rates in CSV format
    csv_url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"
    
    try:
        print("🔄 Downloading ECB historical rates ZIP file...")
        response = requests.get(csv_url, timeout=60)
        
        if response.status_code == 200:
            print("✅ Download successful")
            
            # The ZIP contains a CSV file
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                # Get the CSV file from the ZIP
                csv_filename = zip_file.namelist()[0]  # Usually 'eurofxref-hist.csv'
                
                print(f"📄 Extracting {csv_filename}")
                
                with zip_file.open(csv_filename) as csv_file:
                    df = pd.read_csv(csv_file)
                    
                print(f"✅ Loaded {len(df)} days of data")
                print(f"📅 Date range: {df['Date'].min()} to {df['Date'].max()}")
                print(f"💱 Currencies available: {len(df.columns) - 1}")
                
                return df
        else:
            print(f"❌ Download failed: HTTP {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error downloading data: {str(e)}")
        return None

def create_database():
    """Create SQLite database and exchange_rates table if it doesn't exist"""
    
    try:
        conn = sqlite3.connect('fx_rates.db')
        cursor = conn.cursor()
        
        # Create table for storing exchange rates
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exchange_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                base_currency TEXT NOT NULL,
                target_currency TEXT NOT NULL,
                rate REAL NOT NULL,
                inverse_rate REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, base_currency, target_currency)
            )
        ''')
        
        # Create index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_date_currency 
            ON exchange_rates(date, base_currency, target_currency)
        ''')
        
        conn.commit()
        conn.close()
        
        print("✅ Database and table ready")
        return True
        
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        return False

def process_ecb_csv_data(df, start_date='2024-08-01'):
    """
    Process the downloaded ECB CSV data and convert to GBP base
    """
    
    print(f"\n🔄 Processing ECB CSV data from {start_date}...")
    
    # Filter by start date
    df['Date'] = pd.to_datetime(df['Date'])
    start_dt = pd.to_datetime(start_date)
    df = df[df['Date'] >= start_dt].copy()
    
    print(f"📅 Filtered to {len(df)} days from {start_date}")
    
    # Get available currencies (excluding Date column)
    currencies = [col for col in df.columns if col != 'Date']
    
    # Filter for major currencies we're interested in
    major_currencies = ['USD', 'JPY', 'CHF', 'CAD', 'AUD', 'CNY', 'SEK', 'NOK', 'DKK']
    available_major = [curr for curr in major_currencies if curr in currencies]
    
    print(f"💱 Available major currencies: {', '.join(available_major)}")
    
    if 'GBP' not in currencies:
        print("❌ GBP rates not found in ECB data!")
        return None
    
    # Convert to long format and calculate GBP-based rates
    converted_data = []
    
    for _, row in df.iterrows():
        date_val = row['Date'].date()
        gbp_eur_rate = row['GBP']  # GBP per EUR
        
        if pd.isna(gbp_eur_rate) or gbp_eur_rate == 0:
            continue
            
        # Add EUR/GBP rate (inverse of GBP/EUR)
        eur_gbp_rate = 1 / gbp_eur_rate
        converted_data.append({
            'date': date_val,
            'base_currency': 'GBP',
            'target_currency': 'EUR', 
            'rate': eur_gbp_rate,
            'inverse_rate': gbp_eur_rate
        })
        
        # Add other currencies using triangulation
        for currency in available_major:
            if currency == 'GBP':
                continue
                
            currency_eur_rate = row[currency]  # Currency per EUR
            
            if pd.isna(currency_eur_rate) or currency_eur_rate == 0:
                continue
            
            # Triangulation: (Currency/EUR) ÷ (GBP/EUR) = Currency/GBP
            currency_gbp_rate = currency_eur_rate / gbp_eur_rate
            
            converted_data.append({
                'date': date_val,
                'base_currency': 'GBP',
                'target_currency': currency,
                'rate': currency_gbp_rate,
                'inverse_rate': 1 / currency_gbp_rate if currency_gbp_rate != 0 else 0
            })
    
    result_df = pd.DataFrame(converted_data)
    print(f"✅ Processed {len(result_df)} exchange rate records")
    
    return result_df

def store_ecb_data(df):
    """Store ECB data in the database"""
    
    if df is None or len(df) == 0:
        print("❌ No data to store")
        return False
    
    print(f"\n💾 Storing {len(df)} records in database...")
    
    try:
        conn = sqlite3.connect('fx_rates.db')
        cursor = conn.cursor()
        
        stored_count = 0
        updated_count = 0
        
        for _, row in df.iterrows():
            # Check if record already exists
            cursor.execute(
                "SELECT COUNT(*) FROM exchange_rates WHERE date = ? AND base_currency = ? AND target_currency = ?",
                (row['date'], row['base_currency'], row['target_currency'])
            )
            
            exists = cursor.fetchone()[0] > 0
            
            cursor.execute('''
                INSERT OR REPLACE INTO exchange_rates 
                (date, base_currency, target_currency, rate, inverse_rate)
                VALUES (?, ?, ?, ?, ?)
            ''', (row['date'], row['base_currency'], row['target_currency'], 
                  row['rate'], row['inverse_rate']))
            
            if exists:
                updated_count += 1
            else:
                stored_count += 1
        
        conn.commit()
        conn.close()
        
        print(f"✅ Database updated successfully!")
        print(f"   New records: {stored_count}")
        print(f"   Updated records: {updated_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        return False

def show_database_summary():
    """Show summary of data in database"""
    try:
        conn = sqlite3.connect('fx_rates.db')
        
        # Get overall stats
        query = """
            SELECT 
                MIN(date) as first_date,
                MAX(date) as last_date,
                COUNT(DISTINCT date) as total_days,
                COUNT(DISTINCT target_currency) as total_currencies,
                COUNT(*) as total_records
            FROM exchange_rates 
            WHERE base_currency = 'GBP'
        """
        
        df = pd.read_sql_query(query, conn)
        
        print(f"\n📊 DATABASE SUMMARY")
        print("=" * 40)
        print(f"📅 Date range: {df['first_date'].iloc[0]} to {df['last_date'].iloc[0]}")
        print(f"📆 Total days: {df['total_days'].iloc[0]}")
        print(f"💱 Currencies: {df['total_currencies'].iloc[0]}")
        print(f"📋 Total records: {df['total_records'].iloc[0]:,}")
        
        # Show available currencies
        currency_query = "SELECT DISTINCT target_currency FROM exchange_rates WHERE base_currency = 'GBP' ORDER BY target_currency"
        currencies = pd.read_sql_query(currency_query, conn)
        print(f"💰 Available currencies: {', '.join(currencies['target_currency'].tolist())}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error getting summary: {str(e)}")

def main():
    """Main function to download and import ECB data"""
    
    print("🏦 ECB HISTORICAL EXCHANGE RATE IMPORTER")
    print("=" * 50)
    print("European Central Bank - Official EUR Reference Rates")
    print("Converting to GBP base currency for your dashboard")
    print()
    
    # Create database if it doesn't exist
    if not create_database():
        print("❌ Failed to create database")
        return
    
    # Show current database state
    show_database_summary()
    
    # Download ECB data
    print("\n🔄 DOWNLOADING ECB DATA")
    print("=" * 30)
    
    ecb_df = download_ecb_csv_data()
    
    if ecb_df is not None:
        # Process and convert to GBP base
        converted_df = process_ecb_csv_data(ecb_df, start_date='2024-08-01')
        
        if converted_df is not None:
            # Store in database
            if store_ecb_data(converted_df):
                # Show updated summary
                show_database_summary()
                
                print(f"\n🎉 SUCCESS!")
                print(f"✅ Historical data imported from ECB")
                print(f"✅ Your dashboard now has rich historical data")
                print(f"✅ Try running your Streamlit dashboard to see the new date ranges!")
                print(f"\n📝 To run dashboard: streamlit run fx_dashboard.py")
            else:
                print("❌ Failed to store data in database")
        else:
            print("❌ Failed to process ECB data")
    else:
        print("❌ Failed to download ECB data")

if __name__ == "__main__":
    main()

# =============================================================================
# INSTRUCTIONS
# =============================================================================
print("""
📋 ECB HISTORICAL DATA IMPORTER

WHAT THIS DOES:
✅ Downloads official ECB exchange rate data (completely free)
✅ Converts EUR-based rates to GBP-based rates using triangulation
✅ Imports data from August 2024 to present
✅ Handles weekends and holidays automatically
✅ Won't duplicate existing data

TO RUN:
>>> python ecb_historical_importer.py

NO API KEY NEEDED!
This uses publicly available ECB data.

CURRENCIES INCLUDED:
💰 Major currencies: USD, EUR, JPY, CHF, CAD, AUD, CNY, SEK, NOK, DKK

AFTER RUNNING:
🎯 Your dashboard will have 12+ months of historical data
📊 You can analyze monthly averages and closing rates
📈 Perfect for demonstrating your business logic to employers

TRIANGULATION FORMULA:
Currency/GBP = (Currency/EUR) ÷ (GBP/EUR)
""")