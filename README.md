# 💱 Exchange Rate Dashboard

A professional web application for multi-currency exchange rate analysis, built for financial reporting and EPM systems integration.

## 🎯 Business Problem Solved

Financial organisations require accurate exchange rates for:

- **Income Statement translations** (monthly average rates)
- **Balance Sheet translations** (month-end closing rates)
- **Multi-currency consolidation** in EPM platforms like OneStream
- **Variance analysis** between average and closing rates

## ✨ Key Features

### 📊 **Professional Dashboard**

- Interactive currency selection (Application Currencies)
- Month-by-month analysis with completion status
- Real-time variance calculations
- Export-ready CSV files for EPM systems

### 📈 **Advanced Analytics**

- Average vs Closing rate comparisons
- Variance analysis with colour-coded visualisations
- Data quality indicators
- Historical trend analysis

### 🏦 **Official Data Source**

- European Central Bank (ECB) reference rates
- Over 12 months of historical data
- Automatic currency triangulation (EUR→GBP base)
- Working day calculations (excludes weekends)

## 🚀 Live Demo

**[View Dashboard](https://your-dashboard-url.streamlit.app)** _(Coming Soon)_

## 💻 Technical Stack

- **Backend:** Python, pandas, SQLite
- **Frontend:** Streamlit, Plotly
- **Data Source:** European Central Bank API
- **Deployment:** Streamlit Community Cloud

## 🛠️ Installation & Setup

### Prerequisites

- Python 3.8+
- Git

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/fx-exchange-dashboard.git
cd fx-exchange-dashboard

# Create virtual environment
python -m venv fx_env
source fx_env/Scripts/activate  # Windows Git Bash

# Install dependencies
pip install -r requirements.txt

# Download historical data
python ecb_historical_importer.py

# Run the dashboard
streamlit run fx_dashboard.py
```

## 📁 Project Structure

```
fx-exchange-dashboard/
├── fx_dashboard.py              # Main Streamlit application
├── ecb_historical_importer.py   # ECB data collection script
├── requirements.txt             # Python dependencies
├── README.md                   # Project documentation
└── .gitignore                  # Git exclusion rules
```

## 📊 Data Pipeline

1. **Data Collection:** ECB historical rates (CSV download)
2. **Currency Triangulation:** EUR-based → GBP-based rates
3. **Business Logic:** Calculate monthly averages and closing rates
4. **Visualisation:** Interactive charts and export capabilities

## 🎨 Dashboard Screenshots

### Rate Summary

![Rate Summary](docs/screenshots/rate-summary.png)

### Visualisations

![Charts](docs/screenshots/visualisations.png)

### Export Functionality

![Export](docs/screenshots/export-data.png)

## 🔧 Configuration

### Application Currencies

The dashboard supports configurable "Application Currencies" - the standard currencies used in your organisation's foreign exchange transactions. This mirrors EPM platform functionality.

### Rate Availability

- **Current Month:** Rates available from 1st working day of following month
- **Historical Months:** Complete average and closing rate calculations
- **Data Quality:** Automatic working day calculations

## 📈 Business Logic

### Average Rates

- Calculated across all working days in the month
- Used for Income Statement translations
- Excludes weekends and handles month boundaries

### Closing Rates

- Last working day of the month
- Used for Balance Sheet translations
- Automatic weekend handling

### Variance Analysis

- Absolute variance: Closing Rate - Average Rate
- Percentage variance: (Variance / Average Rate) × 100
- Colour-coded visualisations for immediate insight

## 🎯 Use Cases

### Financial Teams

- Monthly consolidation processes
- Multi-currency reporting
- Rate variance analysis
- EPM system data preparation

### Treasury Teams

- Exchange rate monitoring
- Historical trend analysis
- Rate impact assessment

### Business Intelligence

- Currency exposure analysis
- Financial planning support
- Executive reporting

## 🚀 Deployment

### Streamlit Community Cloud

1. Push code to GitHub
2. Connect repository to Streamlit Cloud
3. Deploy with one click
4. Automatic updates on code changes

### Local Development

```bash
streamlit run fx_dashboard.py
```

## 📊 Data Sources

- **European Central Bank:** Official EUR reference rates
- **Historical Coverage:** August 2024 to present
- **Update Frequency:** Daily (working days)
- **Currencies:** Major international currencies

## 🔮 Future Enhancements

- [ ] Dynamic currency configuration
- [ ] Real-time API integration
- [ ] Multiple base currencies
- [ ] Automated scheduling
- [ ] Advanced trend analysis
- [ ] Rate alerting system

## 👨‍💻 About

Built as a demonstration of:

- **Data integration** and pipeline development
- **Business logic** implementation for financial systems
- **Professional web application** development
- **Real-world problem solving** for multi-currency reporting

## 📞 Contact

**LinkedIn:** [linked.com/in/binepalsingh](https://www.linkedin.com/in/binepalsingh/)
**Email:** binepalsingh@hotmail.com

## 📜 License

MIT License - see [LICENSE](LICENSE) file for details.

---

_Exchange Rate Dashboard - Built with Claude, Python, Streamlit & European Central Bank Data_
