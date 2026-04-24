# BUDA 455 — Final Project

**AI-Powered Business Intelligence for Supplement Sales**

An interactive Streamlit dashboard that integrates supplement sales data with NOAA weather and stock market indicators to uncover demand drivers and provide AI-assisted business insights.

Built for **BUDA 455 — Intro to Business Intelligence & AI**.

---

## Team — Group 6

- Carter Campbell
- Kornelia Buszka
- Timothy Hentnick
- Lydia Reilly

---

## Project Overview

This project blends three data sources into a single analytical pipeline:

1. **Supplement Sales** — transactional product-level sales, returns, and revenue
2. **NOAA Weather** — daily precipitation, temperature, snow, and wind
3. **Stock Market Indicators** — macroeconomic signals for context

The dashboard lets users explore sales trends, seasonality, weather correlations, and category-level performance through interactive Plotly visualizations.

---

## Tech Stack

- **Python 3.10+**
- **Streamlit** — web app framework
- **pandas / numpy** — data wrangling
- **Plotly** — interactive charts

---

## Getting Started

### 1. Clone the repo
```bash
git clone https://github.com/carter-camper/BUDA455_Final.git
cd BUDA455_Final/BUDA455_Final
```

### 2. Create a virtual environment (recommended)
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the app
```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

---

## Project Structure

```
BUDA455_Final/
├── app.py                    # Main Streamlit application
├── requirements.txt          # Python dependencies
├── NOAA_logo.svg             # NOAA logo asset
├── PRESENTATION_SCRIPT.md    # Final presentation script
└── README.md
```

---

## Deployment

The app is deployed on **Streamlit Community Cloud**. Pushes to `master` are automatically redeployed.
