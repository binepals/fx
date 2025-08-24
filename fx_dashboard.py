# fx_dashboard.py - Enhanced with EPM and OneStream Integration Features
# Complete updated version with EPM analytics built in

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import calendar
import os
from io import BytesIO
import json

# =============================================================================
# PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="Exchange Rate Dashboard - EPM Edition",
    page_icon="💱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# EPM ANALYTICS FUNCTIONS (Integrated directly)
# =============================================================================

def calculate_translation_impact_summary(selected_currencies, year):
    """Quick translation impact calculation for dashboard"""
    
    conn = sqlite3.connect('fx_rates.db')
    
    impact_data = []
    current_quarter = (datetime.now().month - 1) // 3 + 1
    
    for quarter in range(1, current_quarter + 1):
        start_month = (quarter - 1) * 3 + 1
        end_month = quarter * 3
        
        for currency in selected_currencies:
            # Get average and closing rates for the quarter
            avg_query = """
                SELECT AVG(rate) as avg_rate
                FROM exchange_rates
                WHERE target_currency = ?
                AND strftime('%Y', date) = ?
                AND CAST(strftime('%m', date) AS INTEGER) BETWEEN ? AND ?
            """
            
            closing_query = """
                SELECT rate as closing_rate
                FROM exchange_rates
                WHERE target_currency = ?
                AND strftime('%Y', date) = ?
                AND CAST(strftime('%m', date) AS INTEGER) = ?
                ORDER BY date DESC
                LIMIT 1
            """
            
            avg_result = conn.execute(avg_query, [currency, str(year), start_month, end_month]).fetchone()
            closing_result = conn.execute(closing_query, [currency, str(year), end_month]).fetchone()
            
            if avg_result and avg_result[0] and closing_result and closing_result[0]:
                avg_rate = avg_result[0]
                closing_rate = closing_result[0]
                impact_pct = ((closing_rate - avg_rate) / avg_rate) * 100
                
                impact_data.append({
                    'quarter': f'Q{quarter}',
                    'currency': currency,
                    'avg_rate': avg_rate,
                    'closing_rate': closing_rate,
                    'translation_impact_pct': impact_pct,
                    'risk_level': 'HIGH' if abs(impact_pct) > 5 else 'MEDIUM' if abs(impact_pct) > 2 else 'LOW'
                })
    
    conn.close()
    return pd.DataFrame(impact_data)

def generate_onestream_export(year, month, selected_currencies):
    """Generate OneStream-compatible export file"""
    
    monthly_data = create_monthly_rate_summary(year, month, selected_currencies)
    
    if len(monthly_data) == 0:
        return None
    
    # OneStream format
    onestream_records = []
    
    for _, row in monthly_data.iterrows():
        # Average rate record (for Income Statement)
        avg_record = {
            'Entity': '[None]',
            'Account': 'FXRate',
            'UD1': row['target_currency'],
            'UD2': 'Average',
            'UD3': '[None]',
            'Time': f"{year}M{month:02d}",
            'Value': row['average_rate'],
            'Annotation': f"Average rate for {calendar.month_name[month]} {year}"
        }
        
        # Closing rate record (for Balance Sheet)
        closing_record = {
            'Entity': '[None]',
            'Account': 'FXRate', 
            'UD1': row['target_currency'],
            'UD2': 'Closing',
            'UD3': '[None]',
            'Time': f"{year}M{month:02d}",
            'Value': row['closing_rate'],
            'Annotation': f"Closing rate for {calendar.month_name[month]} {year}"
        }
        
        onestream_records.extend([avg_record, closing_record])
    
    return pd.DataFrame(onestream_records)

def calculate_volatility_metrics(selected_currencies, days_back=90):
    """Calculate FX volatility for risk assessment"""
    
    conn = sqlite3.connect('fx_rates.db')
    volatility_data = []
    
    for currency in selected_currencies:
        query = """
            SELECT date, rate
            FROM exchange_rates
            WHERE target_currency = ?
            AND date >= date('now', '-{} days')
            ORDER BY date
        """.format(days_back)
        
        df = pd.read_sql_query(query, conn, params=[currency])
        
        if len(df) > 30:
            df['daily_return'] = df['rate'].pct_change()
            current_vol = df['daily_return'].std() * np.sqrt(252) * 100  # Annualized
            
            volatility_data.append({
                'currency': currency,
                'volatility_pct': round(current_vol, 2),
                'risk_category': 'HIGH' if current_vol > 15 else 'MEDIUM' if current_vol > 8 else 'LOW',
                'data_points': len(df)
            })
    
    conn.close()
    return pd.DataFrame(volatility_data)

# =============================================================================
# DATABASE FUNCTIONS
# =============================================================================

def create_currency_config_table():
    """Create table to store user's application currency configuration"""
    try:
        conn = sqlite3.connect('fx_rates.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS application_currencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency_code TEXT UNIQUE NOT NULL,
                currency_name TEXT,
                is_active BOOLEAN DEFAULT 1,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            )
        ''')
        
        # Insert default application currencies if table is empty
        cursor.execute("SELECT COUNT(*) FROM application_currencies")
        if cursor.fetchone()[0] == 0:
            default_currencies = [
                ('USD', 'US Dollar'),
                ('EUR', 'Euro'),
                ('JPY', 'Japanese Yen'),
                ('CAD', 'Canadian Dollar'),
                ('AUD', 'Australian Dollar'),
                ('CHF', 'Swiss Franc'),
                ('CNY', 'Chinese Yuan')
            ]
            
            cursor.executemany(
                "INSERT INTO application_currencies (currency_code, currency_name) VALUES (?, ?)",
                default_currencies
            )
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        st.error(f"Error creating currency config table: {str(e)}")
        return False

def get_application_currencies():
    """Get list of configured application currencies"""
    try:
        conn = sqlite3.connect('fx_rates.db')
        query = """
            SELECT currency_code, currency_name, is_active 
            FROM application_currencies 
            WHERE is_active = 1 
            ORDER BY currency_code
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return df['currency_code'].tolist()
    except:
        # Fallback to default if table doesn't exist
        return ['USD', 'EUR', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY']

def get_all_available_currencies():
    """Get all currencies available in exchange rate data"""
    try:
        conn = sqlite3.connect('fx_rates.db')
        query = "SELECT DISTINCT target_currency FROM exchange_rates ORDER BY target_currency"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df['target_currency'].tolist()
    except:
        return []

def add_application_currency(currency_code, currency_name=None):
    """Add a new currency to application currencies"""
    try:
        conn = sqlite3.connect('fx_rates.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO application_currencies 
            (currency_code, currency_name, is_active) 
            VALUES (?, ?, 1)
        ''', (currency_code, currency_name or currency_code))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        st.error(f"Error adding currency: {str(e)}")
        return False

def remove_application_currency(currency_code):
    """Remove a currency from application currencies (set inactive)"""
    try:
        conn = sqlite3.connect('fx_rates.db')
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE application_currencies SET is_active = 0 WHERE currency_code = ?",
            (currency_code,)
        )
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        st.error(f"Error removing currency: {str(e)}")
        return False

def get_currency_info():
    """Get detailed information about configured currencies"""
    try:
        conn = sqlite3.connect('fx_rates.db')
        query = """
            SELECT 
                ac.currency_code,
                ac.currency_name,
                ac.added_date,
                COUNT(er.id) as data_points,
                MIN(er.date) as first_date,
                MAX(er.date) as last_date
            FROM application_currencies ac
            LEFT JOIN exchange_rates er ON ac.currency_code = er.target_currency
            WHERE ac.is_active = 1
            GROUP BY ac.currency_code, ac.currency_name, ac.added_date
            ORDER BY ac.currency_code
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error getting currency info: {str(e)}")
        return pd.DataFrame()

# =============================================================================
# EXISTING BUSINESS LOGIC FUNCTIONS
# =============================================================================

def get_working_days_in_month(year, month):
    """Get all working days (Monday-Friday) in a given month"""
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    
    working_days = []
    current_date = first_day
    
    while current_date <= last_day:
        if current_date.weekday() < 5:  # Monday to Friday
            working_days.append(current_date)
        current_date += timedelta(days=1)
    
    return working_days

def get_stored_rates(start_date=None, end_date=None, currencies=None):
    """Retrieve stored exchange rates from database"""
    try:
        conn = sqlite3.connect('fx_rates.db')
        
        query = "SELECT * FROM exchange_rates WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
            
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
            
        if currencies:
            placeholders = ','.join(['?' for _ in currencies])
            query += f" AND target_currency IN ({placeholders})"
            params.extend(currencies)
            
        query += " ORDER BY date DESC, target_currency"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return df
            
    except Exception as e:
        st.error(f"Database error: {str(e)}")
        return pd.DataFrame()

def calculate_monthly_averages(year, month, currencies=None):
    """Calculate average exchange rates for a specific month"""
    try:
        conn = sqlite3.connect('fx_rates.db')
        
        working_days = get_working_days_in_month(year, month)
        if not working_days:
            return pd.DataFrame()
        
        start_date = working_days[0]
        end_date = working_days[-1]
        
        query = """
            SELECT target_currency, AVG(rate) as average_rate, AVG(inverse_rate) as average_inverse_rate,
                   COUNT(*) as data_points, MIN(date) as first_date, MAX(date) as last_date
            FROM exchange_rates 
            WHERE base_currency = 'GBP' 
            AND date >= ? AND date <= ?
        """
        params = [start_date, end_date]
        
        if currencies:
            placeholders = ','.join(['?' for _ in currencies])
            query += f" AND target_currency IN ({placeholders})"
            params.extend(currencies)
            
        query += " GROUP BY target_currency ORDER BY target_currency"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if len(df) > 0:
            df['year'] = year
            df['month'] = month
            df['month_name'] = calendar.month_name[month]
            df['working_days_in_month'] = len(working_days)
            df['rate_type'] = 'Average'
            df['average_rate'] = df['average_rate'].round(6)
            df['average_inverse_rate'] = df['average_inverse_rate'].round(6)
            
        return df
            
    except Exception as e:
        st.error(f"Error calculating averages: {str(e)}")
        return pd.DataFrame()

def get_closing_rate(year, month, currencies=None):
    """Get closing exchange rates (last working day) for a specific month"""
    try:
        conn = sqlite3.connect('fx_rates.db')
        
        working_days = get_working_days_in_month(year, month)
        if not working_days:
            return pd.DataFrame()
        
        last_working_day = working_days[-1]
        
        query = """
            SELECT target_currency, rate as closing_rate, inverse_rate as closing_inverse_rate,
                   date as closing_date
            FROM exchange_rates 
            WHERE base_currency = 'GBP' 
            AND date = ?
        """
        params = [last_working_day]
        
        if currencies:
            placeholders = ','.join(['?' for _ in currencies])
            query += f" AND target_currency IN ({placeholders})"
            params.extend(currencies)
            
        query += " ORDER BY target_currency"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if len(df) > 0:
            df['year'] = year
            df['month'] = month
            df['month_name'] = calendar.month_name[month]
            df['last_working_day'] = last_working_day
            df['rate_type'] = 'Closing'
            df['closing_rate'] = df['closing_rate'].round(6)
            df['closing_inverse_rate'] = df['closing_inverse_rate'].round(6)
            
        return df
            
    except Exception as e:
        st.error(f"Error getting closing rates: {str(e)}")
        return pd.DataFrame()

def create_monthly_rate_summary(year, month, currencies=None):
    """Create a comprehensive summary with both average and closing rates"""
    avg_rates = calculate_monthly_averages(year, month, currencies)
    closing_rates = get_closing_rate(year, month, currencies)
    
    if len(avg_rates) == 0 or len(closing_rates) == 0:
        return pd.DataFrame()
    
    summary = pd.merge(
        avg_rates[['target_currency', 'average_rate', 'average_inverse_rate', 'data_points']],
        closing_rates[['target_currency', 'closing_rate', 'closing_inverse_rate', 'closing_date']],
        on='target_currency',
        how='outer'
    )
    
    summary['year'] = year
    summary['month'] = month
    summary['month_name'] = calendar.month_name[month]
    summary['rate_variance'] = (summary['closing_rate'] - summary['average_rate']).round(6)
    summary['variance_percent'] = ((summary['rate_variance'] / summary['average_rate']) * 100).round(2)
    
    return summary

def get_available_months():
    """Get list of available months with data"""
    try:
        conn = sqlite3.connect('fx_rates.db')
        query = """
            SELECT DISTINCT strftime('%Y', date) as year, strftime('%m', date) as month
            FROM exchange_rates 
            ORDER BY year DESC, month DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        months = []
        today = date.today()
        
        for _, row in df.iterrows():
            year = int(row['year'])
            month = int(row['month'])
            
            # Check if this is a complete month
            last_day_of_month = date(year, month, calendar.monthrange(year, month)[1])
            is_complete = last_day_of_month < today
            
            month_name = calendar.month_name[month]
            if is_complete:
                display_name = f"{month_name} {year}"
            else:
                display_name = f"{month_name} {year} (In Progress)"
            
            months.append((year, month, display_name, is_complete))
        
        return months
    except:
        return []

def is_month_complete(year, month):
    """Check if a month is complete"""
    today = date.today()
    last_day_of_month = date(year, month, calendar.monthrange(year, month)[1])
    return last_day_of_month < today

def get_next_working_day(target_date):
    """Get the next working day after the given date"""
    next_day = target_date + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day

# =============================================================================
# CURRENCY CONFIGURATION INTERFACE
# =============================================================================

def currency_management_interface():
    """Interface for managing application currencies"""
    
    st.sidebar.subheader("⚙️ Currency Configuration")
    
    # Initialize currency config table
    create_currency_config_table()
    
    # Expandable section for currency management
    with st.sidebar.expander("🔧 Manage Application Currencies", expanded=False):
        
        # Get current currencies and available currencies
        current_app_currencies = get_application_currencies()
        all_available_currencies = get_all_available_currencies()
        
        # Show current application currencies
        st.write("**Current Application Currencies:**")
        if current_app_currencies:
            cols = st.columns(2)
            for i, curr in enumerate(current_app_currencies):
                col_idx = i % 2
                with cols[col_idx]:
                    st.text(f"• {curr}")
        else:
            st.warning("No application currencies configured")
        
        st.divider()
        
        # Add new currency
        st.write("**Add New Currency:**")
        
        # Available currencies not yet in application list
        available_to_add = [curr for curr in all_available_currencies if curr not in current_app_currencies]
        
        if available_to_add:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                new_currency = st.selectbox(
                    "Select currency to add:",
                    [""] + available_to_add,
                    key="add_currency_select"
                )
            
            with col2:
                if st.button("➕ Add", key="add_currency_btn", disabled=not new_currency):
                    if new_currency:
                        if add_application_currency(new_currency):
                            st.success(f"✅ Added {new_currency}")
                            st.rerun()
                        else:
                            st.error("Failed to add currency")
        else:
            st.info("All available currencies are already configured")
        
        st.divider()
        
        # Remove existing currency
        st.write("**Remove Currency:**")
        
        if len(current_app_currencies) > 1:  # Ensure at least one currency remains
            col1, col2 = st.columns([3, 1])
            
            with col1:
                remove_currency = st.selectbox(
                    "Select currency to remove:",
                    [""] + current_app_currencies,
                    key="remove_currency_select"
                )
            
            with col2:
                if st.button("🗑️ Remove", key="remove_currency_btn", disabled=not remove_currency):
                    if remove_currency:
                        if remove_application_currency(remove_currency):
                            st.success(f"✅ Removed {remove_currency}")
                            st.rerun()
                        else:
                            st.error("Failed to remove currency")
        else:
            st.info("Must have at least one application currency")
        
        st.divider()
        
        # Currency information
        if st.button("📊 Show Currency Details", key="show_currency_info"):
            st.session_state.show_currency_details = not st.session_state.get('show_currency_details', False)
        
        if st.session_state.get('show_currency_details', False):
            currency_info = get_currency_info()
            if len(currency_info) > 0:
                st.dataframe(
                    currency_info[['currency_code', 'currency_name', 'data_points', 'first_date', 'last_date']],
                    column_config={
                        "currency_code": "Currency",
                        "currency_name": "Name", 
                        "data_points": "Data Points",
                        "first_date": "First Date",
                        "last_date": "Last Date"
                    },
                    hide_index=True
                )

# =============================================================================
# STREAMLIT DASHBOARD
# =============================================================================

def main():
    # Header
    st.title("💱 Exchange Rate Dashboard")
    st.markdown("**Multi-Currency Exchange Rate Analysis for EPM & OneStream Integration**")
    st.markdown("*Base Currency: GBP | Enhanced for EPM Professionals & OneStream Customers*")
    
    # Check if database exists
    if not os.path.exists('fx_rates.db'):
        st.error("❌ Database not found! Please run the enhanced ECB data collection script first.")
        st.stop()
    
    # Sidebar - Configuration
    st.sidebar.header("📊 Configuration")
    
    # Currency Configuration Management
    currency_management_interface()
    
    # EPM Features Section
    st.sidebar.subheader("🏦 EPM Features")
    
    epm_mode = st.sidebar.checkbox(
        "Enable EPM Analytics",
        value=True,
        help="Show OneStream integration and EPM-specific analysis features"
    )
    
    if epm_mode:
        export_format = st.sidebar.selectbox(
            "Export Format:",
            ["Standard CSV", "OneStream Import File", "EPM Analysis Package"],
            help="Choose export format for your EPM system"
        )
        
        risk_analysis = st.sidebar.checkbox(
            "Include Risk Analysis",
            value=True,
            help="Add FX volatility and translation risk metrics"
        )
    
    # Get configured currencies
    available_currencies = get_all_available_currencies() 
    application_currencies = get_application_currencies()
    available_months = get_available_months()
    
    if not available_currencies:
        st.error("❌ No exchange rate data found! Please run the enhanced ECB data collection script first.")
        st.stop()
    
    # Currency Selection - Now uses dynamic configuration
    st.sidebar.subheader("💱 Currency Selection")
    
    currency_mode = st.sidebar.radio(
        "Select currencies:",
        ["Application Currencies", "Custom Selection", "All Available"],
        help="Application Currencies are configured in the Currency Configuration section above"
    )
    
    if currency_mode == "Application Currencies":
        if application_currencies:
            selected_currencies = st.sidebar.multiselect(
                "Application currencies:",
                application_currencies,
                default=application_currencies,
                help="Currencies configured for your organisation's foreign exchange transactions"
            )
        else:
            st.sidebar.warning("No application currencies configured. Use the configuration panel above.")
            selected_currencies = []
            
    elif currency_mode == "Custom Selection":
        selected_currencies = st.sidebar.multiselect(
            "Choose currencies:",
            available_currencies,
            default=application_currencies[:3] if application_currencies else available_currencies[:3]
        )
    else:
        selected_currencies = available_currencies
        st.sidebar.info(f"All {len(available_currencies)} available currencies selected")
    
    # Time Period Selection
    st.sidebar.subheader("📅 Time Period")
    
    if available_months:
        # Find the latest complete month as default
        complete_months = [(year, month, display_name) for year, month, display_name, is_complete in available_months if is_complete]
        
        if complete_months:
            month_options = {display_name: (year, month) for year, month, display_name in complete_months}
        else:
            month_options = {display_name: (year, month) for year, month, display_name, _ in available_months}
        
        selected_month_name = st.sidebar.selectbox(
            "Select month:",
            list(month_options.keys()),
            index=0,
            help="Rates for current month available from 1st working day of following month"
        )
        
        selected_year, selected_month = month_options[selected_month_name]
    else:
        st.error("❌ No data available for any months")
        st.stop()
    
    # Check if selected month is complete
    month_is_complete = is_month_complete(selected_year, selected_month)
    
    # Main Dashboard
    if selected_currencies:
        
        # Enhanced display current selection with metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("📅 Selected Period", f"{calendar.month_name[selected_month]} {selected_year}")
        with col2:
            st.metric("💱 Selected Currencies", len(selected_currencies))
        with col3:
            st.metric("⚙️ Application Currencies", len(application_currencies))
        with col4:
            working_days = len(get_working_days_in_month(selected_year, selected_month))
            st.metric("📊 Working Days", working_days)
        with col5:
            # Enhanced metric - total data coverage
            total_records = len(get_stored_rates(currencies=selected_currencies))
            st.metric("📋 Total Data Points", f"{total_records:,}")
        
        # Month status indicator
        if not month_is_complete:
            last_day = date(selected_year, selected_month, calendar.monthrange(selected_year, selected_month)[1])
            next_working_day = get_next_working_day(last_day)
            st.info(f"ℹ️ **Month in Progress:** Average and Closing rates for {calendar.month_name[selected_month]} {selected_year} will be available from {next_working_day.strftime('%d %B %Y')} (first working day of following month)")
        
        # EPM Context Banner
        if epm_mode:
            st.info("🏦 **EPM Mode Active**: Enhanced analytics for OneStream integration, FX risk assessment, and consolidation reporting")
        
        st.divider()
        
        # Get data
        summary_data = create_monthly_rate_summary(selected_year, selected_month, selected_currencies)
        
        if len(summary_data) > 0:
            
            # Enhanced tab layout with EPM features
            if epm_mode:
                tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                    "📊 Rate Summary", 
                    "📈 Visualisations", 
                    "🏦 EPM Analytics",
                    "📁 Export Data", 
                    "📋 Raw Data", 
                    "⚙️ Configuration"
                ])
            else:
                tab1, tab2, tab3, tab4, tab5 = st.tabs([
                    "📊 Rate Summary", 
                    "📈 Visualisations", 
                    "📁 Export Data", 
                    "📋 Raw Data", 
                    "⚙️ Configuration"
                ])
            
            with tab1:
                st.subheader("💱 Exchange Rate Summary")
                
                # Key metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    avg_variance = summary_data['variance_percent'].abs().mean()
                    st.metric("📊 Avg Variance", f"{avg_variance:.2f}%")
                
                with col2:
                    max_variance = summary_data['variance_percent'].abs().max()
                    st.metric("📈 Max Variance", f"{max_variance:.2f}%")
                
                with col3:
                    avg_data_points = summary_data['data_points'].mean()
                    st.metric("📋 Avg Data Points", f"{avg_data_points:.1f}")
                
                with col4:
                    last_update = summary_data['closing_date'].iloc[0] if len(summary_data) > 0 else "N/A"
                    st.metric("📅 Last Update", last_update)
                
                # EPM Context
                if epm_mode:
                    st.info("💼 **EPM Context**: Average rates used for Income Statement translation, Closing rates for Balance Sheet positions")
                
                # Summary table with EPM column names
                st.subheader("📋 Rate Details")
                
                display_df = summary_data[[
                    'target_currency', 'average_rate', 'closing_rate', 
                    'rate_variance', 'variance_percent', 'data_points'
                ]].copy()
                
                if epm_mode:
                    display_df.columns = [
                        'Currency', 'Average Rate (P&L)', 'Closing Rate (B/S)', 
                        'Variance', 'Variance %', 'Data Points'
                    ]
                else:
                    display_df.columns = [
                        'Currency', 'Average Rate', 'Closing Rate', 
                        'Variance', 'Variance %', 'Data Points'
                    ]
                
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    column_config={
                        "Average Rate (P&L)" if epm_mode else "Average Rate": st.column_config.NumberColumn(format="%.6f"),
                        "Closing Rate (B/S)" if epm_mode else "Closing Rate": st.column_config.NumberColumn(format="%.6f"),
                        "Variance": st.column_config.NumberColumn(format="%.6f"),
                        "Variance %": st.column_config.NumberColumn(format="%.2f%%"),
                    }
                )
            
            with tab2:
                st.subheader("📈 Exchange Rate Visualisations")
                
                # Chart 1: Average vs Closing Rates
                fig1 = go.Figure()
                
                fig1.add_trace(go.Bar(
                    name='Average Rate' if not epm_mode else 'Average Rate (P&L)',
                    x=summary_data['target_currency'],
                    y=summary_data['average_rate'],
                    marker_color='lightblue'
                ))
                
                fig1.add_trace(go.Bar(
                    name='Closing Rate' if not epm_mode else 'Closing Rate (B/S)', 
                    x=summary_data['target_currency'],
                    y=summary_data['closing_rate'],
                    marker_color='orange'
                ))
                
                fig1.update_layout(
                    title=f'Average vs Closing Rates - {calendar.month_name[selected_month]} {selected_year}' + (' (EPM View)' if epm_mode else ''),
                    xaxis_title='Currency',
                    yaxis_title='Exchange Rate (1 GBP =)',
                    barmode='group',
                    height=400
                )
                
                st.plotly_chart(fig1, use_container_width=True)
                
                # Chart 2: Variance Analysis
                fig2 = px.bar(
                    summary_data,
                    x='target_currency',
                    y='variance_percent',
                    title='Rate Variance Analysis (%)' + (' - Translation Impact' if epm_mode else ''),
                    color='variance_percent',
                    color_continuous_scale='RdYlBu_r'
                )
                
                fig2.update_layout(
                    xaxis_title='Currency',
                    yaxis_title='Variance (%)' + (' - Translation Risk' if epm_mode else ''),
                    height=400
                )
                
                st.plotly_chart(fig2, use_container_width=True)
                
                # Chart 3: Data Quality
                fig3 = px.bar(
                    summary_data,
                    x='target_currency',
                    y='data_points',
                    title='Data Quality - Points per Currency',
                    color='data_points',
                    color_continuous_scale='Greens'
                )
                
                fig3.update_layout(
                    xaxis_title='Currency',
                    yaxis_title='Number of Data Points',
                    height=400
                )
                
                st.plotly_chart(fig3, use_container_width=True)
            
            # NEW EPM ANALYTICS TAB
            if epm_mode:
                with tab3:
                    st.subheader("🏦 EPM & OneStream Analytics")
                    
                    # Translation Impact Analysis
                    st.markdown("### 📊 Translation Impact Analysis")
                    st.markdown("*Critical for understanding FX impact on consolidated financial statements*")
                    
                    if risk_analysis:
                        # Calculate translation impacts
                        translation_data = calculate_translation_impact_summary(selected_currencies, selected_year)
                        
                        if len(translation_data) > 0:
                            # Translation impact chart
                            fig_translation = px.bar(
                                translation_data,
                                x='currency',
                                y='translation_impact_pct',
                                color='risk_level',
                                facet_col='quarter',
                                title='Translation Impact by Quarter (%)',
                                color_discrete_map={'HIGH': 'red', 'MEDIUM': 'orange', 'LOW': 'green'}
                            )
                            
                            st.plotly_chart(fig_translation, use_container_width=True)
                            
                            # Summary metrics
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                high_risk_count = len(translation_data[translation_data['risk_level'] == 'HIGH'])
                                st.metric("🔴 High Risk Currencies", high_risk_count)
                            
                            with col2:
                                max_impact = translation_data['translation_impact_pct'].abs().max()
                                st.metric("📈 Max Translation Impact", f"{max_impact:.2f}%")
                            
                            with col3:
                                avg_impact = translation_data['translation_impact_pct'].abs().mean()
                                st.metric("📊 Average Impact", f"{avg_impact:.2f}%")
                        else:
                            st.info("📊 Translation impact analysis requires quarterly data. Select a complete quarter to see analysis.")
                    
                    # FX Volatility Risk Assessment
                    st.markdown("### ⚠️ FX Volatility Risk Assessment")
                    st.markdown("*90-day rolling volatility analysis for hedging decisions*")
                    
                    volatility_data = calculate_volatility_metrics(selected_currencies)
                    
                    if len(volatility_data) > 0:
                        # Volatility risk chart
                        fig_vol = px.bar(
                            volatility_data,
                            x='currency',
                            y='volatility_pct',
                            color='risk_category',
                            title='FX Volatility Risk Assessment (90-day Annualized)',
                            color_discrete_map={'HIGH': 'red', 'MEDIUM': 'orange', 'LOW': 'green'}
                        )
                        
                        fig_vol.add_hline(y=15, line_dash="dash", line_color="red", 
                                         annotation_text="High Risk Threshold")
                        fig_vol.add_hline(y=8, line_dash="dash", line_color="orange", 
                                         annotation_text="Medium Risk Threshold")
                        
                        st.plotly_chart(fig_vol, use_container_width=True)
                        
                        # Volatility summary table
                        st.dataframe(
                            volatility_data[['currency', 'volatility_pct', 'risk_category']],
                            column_config={
                                'volatility_pct': st.column_config.NumberColumn('Volatility %', format='%.2f%%'),
                                'risk_category': st.column_config.TextColumn('Risk Level')
                            }
                        )
                        
                        # Risk recommendations
                        high_risk_currencies = volatility_data[volatility_data['risk_category'] == 'HIGH']['currency'].tolist()
                        if high_risk_currencies:
                            st.warning(f"⚠️ **High Risk Currencies**: {', '.join(high_risk_currencies)}")
                            st.markdown("**Recommended Actions:**")
                            st.markdown("- Consider active hedging strategies")
                            st.markdown("- Increase monitoring frequency") 
                            st.markdown("- Review exposure limits")
                        else:
                            st.success("✅ All currencies within acceptable volatility ranges")
                    
                    # OneStream Integration Preview
                    st.markdown("### 🔗 OneStream Integration Preview")
                    
                    if st.button("🎯 Generate OneStream Import Preview"):
                        onestream_preview = generate_onestream_export(selected_year, selected_month, selected_currencies[:3])  # Limit for preview
                        
                        if onestream_preview is not None:
                            st.markdown("**OneStream Import File Format:**")
                            st.dataframe(onestream_preview.head(10))
                            st.info("💡 Full export available in Export Data tab")
                        else:
                            st.warning("No data available for OneStream export preview")
            
            # Enhanced Export Tab
            with tab4 if epm_mode else tab3:
                st.subheader("📁 Export Exchange Rates")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if epm_mode:
                        st.info("🏦 **EPM Integration Ready**\n\nExport formats:\n- **OneStream**: Direct import file\n- **Standard**: Multi-purpose CSV\n- **EPM Package**: Complete analysis suite")
                    else:
                        st.info("💼 **Business Use Case**\n\nExport rates for EPM systems like OneStream:\n- Average rates for Income Statement\n- Closing rates for Balance Sheet")
                
                with col2:
                    if epm_mode and export_format == "OneStream Import File":
                        # OneStream export
                        onestream_data = generate_onestream_export(selected_year, selected_month, selected_currencies)
                        
                        if onestream_data is not None:
                            csv_buffer = BytesIO()
                            onestream_data.to_csv(csv_buffer, index=False)
                            csv_data = csv_buffer.getvalue()
                            
                            filename = f"OneStream_FXRates_{selected_year}M{selected_month:02d}.csv"
                            
                            st.download_button(
                                label="📥 Download OneStream File",
                                data=csv_data,
                                file_name=filename,
                                mime="text/csv",
                                use_container_width=True
                            )
                            
                            st.success(f"✅ OneStream import file ready ({len(onestream_data)} rate records)")
                        else:
                            st.warning("No OneStream data available for selected period")
                    
                    elif epm_mode and export_format == "EPM Analysis Package":
                        # Complete EPM package with multiple files
                        st.markdown("**EPM Analysis Package includes:**")
                        st.markdown("- Exchange rate data")
                        st.markdown("- Translation impact analysis")
                        st.markdown("- Volatility risk assessment") 
                        st.markdown("- OneStream import file")
                        
                        if st.button("📦 Generate EPM Package", use_container_width=True):
                            st.info("📦 EPM Analysis Package generation - Feature coming soon!")
                            st.markdown("Package will include multiple Excel sheets with comprehensive analysis")
                    
                    else:
                        # Standard CSV export
                        export_df = summary_data[[
                            'target_currency', 'average_rate', 'closing_rate', 
                            'average_inverse_rate', 'closing_inverse_rate',
                            'rate_variance', 'variance_percent', 'data_points',
                            'closing_date', 'month_name', 'year'
                        ]].copy()
                        
                        export_df.columns = [
                            'Currency', 'Average_Rate_GBP', 'Closing_Rate_GBP',
                            'Average_Inverse_Rate', 'Closing_Inverse_Rate', 
                            'Rate_Variance', 'Variance_Percent', 'Data_Points',
                            'Closing_Date', 'Month', 'Year'
                        ]
                        
                        csv_buffer = BytesIO()
                        export_df.to_csv(csv_buffer, index=False)
                        csv_data = csv_buffer.getvalue()
                        
                        filename = f"fx_rates_{selected_year}_{selected_month:02d}_{len(selected_currencies)}currencies.csv"
                        
                        st.download_button(
                            label="📥 Download Standard CSV",
                            data=csv_data,
                            file_name=filename,
                            mime="text/csv",
                            use_container_width=True
                        )
                        
                        st.success(f"✅ Ready to export {len(export_df)} currency rates")
            
            # Raw Data Tab
            with tab5 if epm_mode else tab4:
                st.subheader("📋 Raw Exchange Rate Data")
                
                # Show recent daily rates
                recent_data = get_stored_rates(
                    start_date=date(selected_year, selected_month, 1),
                    end_date=date(selected_year, selected_month, calendar.monthrange(selected_year, selected_month)[1]),
                    currencies=selected_currencies
                )
                
                if len(recent_data) > 0:
                    st.dataframe(
                        recent_data[['date', 'target_currency', 'rate', 'inverse_rate']],
                        use_container_width=True,
                        column_config={
                            "rate": st.column_config.NumberColumn(format="%.6f"),
                            "inverse_rate": st.column_config.NumberColumn(format="%.6f"),
                        }
                    )
                    
                    st.info(f"📊 Showing {len(recent_data)} daily rate records")
                else:
                    st.warning("No raw data available for selected period")
            
            # Configuration Tab
            with tab6 if epm_mode else tab5:
                st.subheader("⚙️ Currency Configuration Details")
                
                # Comprehensive currency information
                currency_info = get_currency_info()
                
                if len(currency_info) > 0:
                    st.write("**Application Currency Analysis:**")
                    
                    # Enhanced currency info display
                    for _, row in currency_info.iterrows():
                        with st.container():
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                st.metric(
                                    label=f"💱 {row['currency_code']}", 
                                    value=row['currency_name'] or row['currency_code']
                                )
                            
                            with col2:
                                st.metric(
                                    label="📊 Data Points",
                                    value=f"{row['data_points']:,}" if row['data_points'] else "0"
                                )
                            
                            with col3:
                                st.metric(
                                    label="📅 First Date",
                                    value=row['first_date'] if row['first_date'] else "No data"
                                )
                            
                            with col4:
                                st.metric(
                                    label="📅 Last Date", 
                                    value=row['last_date'] if row['last_date'] else "No data"
                                )
                    
                    st.divider()
                    
                    # Configuration summary
                    total_currencies = len(currency_info)
                    total_data_points = currency_info['data_points'].sum()
                    avg_data_points = currency_info['data_points'].mean()
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("🔢 Total Currencies", total_currencies)
                    with col2:
                        st.metric("📊 Total Data Points", f"{total_data_points:,}")
                    with col3:
                        st.metric("📈 Avg per Currency", f"{avg_data_points:.0f}")
                
                else:
                    st.warning("No currency configuration data available")
                
                # Data coverage analysis
                st.subheader("📊 Data Coverage Analysis")
                
                # Show which configured currencies have data vs which don't
                configured_currencies = set(application_currencies)
                currencies_with_data = set(currency_info['currency_code'].tolist())
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**✅ Currencies with Data:**")
                    currencies_with_data_list = list(currencies_with_data)
                    if currencies_with_data_list:
                        for curr in sorted(currencies_with_data_list):
                            st.text(f"• {curr}")
                    else:
                        st.warning("No currencies have data")
                
                with col2:
                    missing_data = configured_currencies - currencies_with_data
                    st.write("**⚠️ Currencies Missing Data:**")
                    if missing_data:
                        for curr in sorted(missing_data):
                            st.text(f"• {curr}")
                        st.info("💡 Run enhanced ECB importer to collect data for these currencies")
                    else:
                        st.success("All configured currencies have data!")
        
        else:
            if not month_is_complete:
                st.info(f"ℹ️ **Rates Not Yet Available:** Average and Closing rates for {calendar.month_name[selected_month]} {selected_year} will be calculated and available from the first working day of {calendar.month_name[selected_month + 1 if selected_month < 12 else 1]} {selected_year if selected_month < 12 else selected_year + 1}")
            else:
                st.warning(f"❌ No data available for {calendar.month_name[selected_month]} {selected_year}")
                st.info("💡 Make sure you have run the enhanced ECB data collection script for this time period")
    
    else:
        st.warning("⚠️ Please select at least one currency to analyse")
        
        # Show helpful guidance when no currencies selected
        if currency_mode == "Application Currencies" and not application_currencies:
            st.info("💡 **Getting Started:** Use the Currency Configuration panel in the sidebar to set up your organisation's application currencies")
    
    # Enhanced footer
    st.divider()
    if epm_mode:
        st.markdown("*EPM Exchange Rate Dashboard - OneStream Integration Ready | Built with Claude, Python, Streamlit & ECB Data*")
        st.markdown("🎯 **Target Audience**: OneStream Customers, EPM Consultants, Corporate Finance Teams")
        
        # Add professional credentials section
        with st.expander("📋 Technical Specifications", expanded=False):
            st.markdown("**Data Sources**: European Central Bank (ECB) Official Reference Rates")
            st.markdown("**Update Frequency**: Daily (working days only)")
            st.markdown("**Base Currency**: GBP (British Pound)")
            st.markdown("**Export Formats**: CSV, OneStream Import Files")
            st.markdown("**Risk Analytics**: 90-day rolling volatility, translation impact analysis")
            st.markdown("**Compliance**: Working day logic, audit trail, data validation")
    else:
        st.markdown("*Exchange Rate Dashboard - Built with Claude, Python, Streamlit & European Central Bank Data*")

if __name__ == "__main__":
    main()