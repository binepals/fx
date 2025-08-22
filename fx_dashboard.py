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

# =============================================================================
# PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="Exchange Rate Dashboard",
    page_icon="💱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# BUSINESS LOGIC FUNCTIONS
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

def get_available_currencies():
    """Get list of all available currencies in database"""
    try:
        conn = sqlite3.connect('fx_rates.db')
        query = "SELECT DISTINCT target_currency FROM exchange_rates ORDER BY target_currency"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df['target_currency'].tolist()
    except:
        return []

def get_available_months():
    """Get list of available months with data, defaulting to latest complete month"""
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
            
            # Check if this is a complete month (last day has passed)
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
    """Check if a month is complete (all working days have passed)"""
    today = date.today()
    last_day_of_month = date(year, month, calendar.monthrange(year, month)[1])
    return last_day_of_month < today

def get_next_working_day(target_date):
    """Get the next working day after the given date"""
    next_day = target_date + timedelta(days=1)
    while next_day.weekday() >= 5:  # Skip weekends
        next_day += timedelta(days=1)
    return next_day

# =============================================================================
# STREAMLIT DASHBOARD
# =============================================================================

def main():
    # Header
    st.title("💱 Exchange Rate Dashboard")
    st.markdown("**Multi-Currency Exchange Rate Analysis for Financial Reporting**")
    st.markdown("*Base Currency: GBP (British Pound)*")
    
    # Check if database exists
    if not os.path.exists('fx_rates.db'):
        st.error("❌ Database not found! Please run the ECB data collection script first.")
        st.stop()
    
    # Sidebar - Configuration
    st.sidebar.header("📊 Configuration")
    
    # Get available data
    available_currencies = get_available_currencies()
    available_months = get_available_months()
    
    if not available_currencies:
        st.error("❌ No exchange rate data found! Please run the ECB data collection script first.")
        st.stop()
    
    # Currency Selection - Updated for Application Currencies
    st.sidebar.subheader("💱 Currency Selection")
    
    # Application currency groups (common business currencies)
    application_currencies = ['USD', 'EUR', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY']
    available_application = [curr for curr in application_currencies if curr in available_currencies]
    
    currency_mode = st.sidebar.radio(
        "Select currencies:",
        ["Application Currencies", "Custom Selection", "All Available"]
    )
    
    if currency_mode == "Application Currencies":
        selected_currencies = st.sidebar.multiselect(
            "Application currencies:",
            available_application,
            default=available_application[:5] if len(available_application) >= 5 else available_application,
            help="Standard currencies used in your organisation's foreign exchange transactions"
        )
    elif currency_mode == "Custom Selection":
        selected_currencies = st.sidebar.multiselect(
            "Choose currencies:",
            available_currencies,
            default=available_application[:3] if available_application else available_currencies[:3]
        )
    else:
        selected_currencies = available_currencies
        st.sidebar.info(f"All {len(available_currencies)} available currencies selected")
    
    # Time Period Selection - Updated for latest complete month default
    st.sidebar.subheader("📅 Time Period")
    
    if available_months:
        # Find the latest complete month as default
        complete_months = [(year, month, display_name) for year, month, display_name, is_complete in available_months if is_complete]
        
        if complete_months:
            month_options = {display_name: (year, month) for year, month, display_name in complete_months}
            default_selection = list(month_options.keys())[0]  # Latest complete month
        else:
            # If no complete months, show all with indicators
            month_options = {display_name: (year, month) for year, month, display_name, _ in available_months}
            default_selection = list(month_options.keys())[0]
        
        selected_month_name = st.sidebar.selectbox(
            "Select month:",
            list(month_options.keys()),
            index=0,  # Default to first (latest) month
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
        
        # Display current selection
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📅 Selected Period", f"{calendar.month_name[selected_month]} {selected_year}")
        with col2:
            st.metric("💱 Currencies", len(selected_currencies))
        with col3:
            working_days = len(get_working_days_in_month(selected_year, selected_month))
            st.metric("📊 Working Days", working_days)
        
        # Month status indicator
        if not month_is_complete:
            last_day = date(selected_year, selected_month, calendar.monthrange(selected_year, selected_month)[1])
            next_working_day = get_next_working_day(last_day)
            st.info(f"ℹ️ **Month in Progress:** Average and Closing rates for {calendar.month_name[selected_month]} {selected_year} will be available from {next_working_day.strftime('%d %B %Y')} (first working day of following month)")
        
        st.divider()
        
        # Get data
        summary_data = create_monthly_rate_summary(selected_year, selected_month, selected_currencies)
        
        if len(summary_data) > 0:
            
            # Tab layout - Updated spelling
            tab1, tab2, tab3, tab4 = st.tabs(["📊 Rate Summary", "📈 Visualisations", "📁 Export Data", "📋 Raw Data"])
            
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
                
                # Summary table
                st.subheader("📋 Rate Details")
                
                display_df = summary_data[[
                    'target_currency', 'average_rate', 'closing_rate', 
                    'rate_variance', 'variance_percent', 'data_points'
                ]].copy()
                
                display_df.columns = [
                    'Currency', 'Average Rate', 'Closing Rate', 
                    'Variance', 'Variance %', 'Data Points'
                ]
                
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    column_config={
                        "Average Rate": st.column_config.NumberColumn(format="%.6f"),
                        "Closing Rate": st.column_config.NumberColumn(format="%.6f"),
                        "Variance": st.column_config.NumberColumn(format="%.6f"),
                        "Variance %": st.column_config.NumberColumn(format="%.2f%%"),
                    }
                )
            
            with tab2:
                st.subheader("📈 Exchange Rate Visualisations")
                
                # Chart 1: Average vs Closing Rates
                fig1 = go.Figure()
                
                fig1.add_trace(go.Bar(
                    name='Average Rate',
                    x=summary_data['target_currency'],
                    y=summary_data['average_rate'],
                    marker_color='lightblue'
                ))
                
                fig1.add_trace(go.Bar(
                    name='Closing Rate', 
                    x=summary_data['target_currency'],
                    y=summary_data['closing_rate'],
                    marker_color='orange'
                ))
                
                fig1.update_layout(
                    title=f'Average vs Closing Rates - {calendar.month_name[selected_month]} {selected_year}',
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
                    title='Rate Variance Analysis (%)',
                    color='variance_percent',
                    color_continuous_scale='RdYlBu_r'
                )
                
                fig2.update_layout(
                    xaxis_title='Currency',
                    yaxis_title='Variance (%)',
                    height=400
                )
                
                st.plotly_chart(fig2, use_container_width=True)
                
                # Chart 3: Data Quality
                fig3 = px.bar(
                    summary_data,
                    x='target_currency',
                    y='data_points',
                    title='Data Points per Currency',
                    color='data_points',
                    color_continuous_scale='Greens'
                )
                
                fig3.update_layout(
                    xaxis_title='Currency',
                    yaxis_title='Number of Data Points',
                    height=400
                )
                
                st.plotly_chart(fig3, use_container_width=True)
            
            with tab3:
                st.subheader("📁 Export Exchange Rates")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.info("💼 **Business Use Case**\n\nExport rates for EPM systems like OneStream:\n- Average rates for Income Statement\n- Closing rates for Balance Sheet\n- Ready for multi-currency consolidation")
                
                with col2:
                    # Prepare export data
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
                    
                    # Convert to CSV
                    csv_buffer = BytesIO()
                    export_df.to_csv(csv_buffer, index=False)
                    csv_data = csv_buffer.getvalue()
                    
                    filename = f"fx_rates_{selected_year}_{selected_month:02d}_{len(selected_currencies)}currencies.csv"
                    
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv_data,
                        file_name=filename,
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                    st.success(f"✅ Ready to export {len(export_df)} currency rates")
            
            with tab4:
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
        
        else:
            if not month_is_complete:
                st.info(f"ℹ️ **Rates Not Yet Available:** Average and Closing rates for {calendar.month_name[selected_month]} {selected_year} will be calculated and available from the first working day of {calendar.month_name[selected_month + 1 if selected_month < 12 else 1]} {selected_year if selected_month < 12 else selected_year + 1}")
            else:
                st.warning(f"❌ No data available for {calendar.month_name[selected_month]} {selected_year}")
                st.info("💡 Make sure you have run the ECB data collection script for this time period")
    
    else:
        st.warning("⚠️ Please select at least one currency to analyse")
    
    # Footer - Updated citation
    st.divider()
    st.markdown("*Exchange Rate Dashboard - Built with Claude, Python, Streamlit & European Central Bank Data*")

if __name__ == "__main__":
    main()
