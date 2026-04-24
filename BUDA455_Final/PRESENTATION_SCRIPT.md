# BUDA 455 Final Presentation Script
**AI-Powered BI for Data-Driven Decision Making**
*~2.5 minutes per person | 10 minutes total*

---

## Timing Guide

| Person | Section | Time |
|--------|---------|------|
| Person 1 | Business Overview + Data Integration | 0:00 – 2:30 |
| Person 2 | Data Transformation | 2:30 – 5:00 |
| Person 3 | BI Analysis + Key Findings | 5:00 – 7:30 |
| Person 4 | AI Assistant + Conclusion | 7:30 – 10:00 |

---

## PERSON 1 — Business Overview & Data Integration (0:00 – 2:30)

> Navigate to the **Business Overview** page on the dashboard while speaking.

"Good [morning/afternoon] everyone. Our project tackles a real business question:

**How do weather conditions and e-commerce stock market performance influence supplement product
sales across Amazon, Walmart, and iHerb in the USA and Canada from 2020 to 2025?**

This matters because supplement retailers spend millions on inventory planning and promotions.
Understanding whether a cold week or a bull market actually moves sales can directly improve
those decisions.

To answer this, we built a complete end-to-end BI pipeline using three independent data sources:

- **Source 1** — Weekly supplement sales data from Kaggle covering 16 products across 3 platforms
  and 3 markets
- **Source 2** — NOAA Climate Data Online, which was required by the project — daily weather
  observations from Charleston, WV
- **Source 3** — World Stock Prices Dataset from Kaggle, covering five major U.S. retail and
  e-commerce companies

> Navigate to the **Data Integration** page.

We joined all three on a common `week_start` key — a Monday-aligned weekly period. NOAA's daily
data was aggregated up to weekly, and so were the daily stock prices. This gave us a master
dataset of **4,384 rows and 26 columns with zero missing values** — well above the minimum
requirements of 1,000 observations and 10 variables."

---

## PERSON 2 — Data Transformation (2:30 – 5:00)

> Navigate to the **Data Transformation** page.

"Once we had our integrated dataset, we applied 11 data transformation techniques from Chapter 14
to prepare it for analysis.

Starting with **arithmetic and derived variables** — we created metrics like `revenue_per_unit`,
`discount_usd`, and `temp_swing_f` which measures daily temperature volatility in a given week.
These aren't in the raw data — we engineered them to capture business-relevant signals.

We also created **time-series lag features** — specifically `revenue_lag_1`, the prior week's
revenue grouped by product and location. This is a panel data best practice that prevents revenue
from one product bleeding into another's lag.

For scaling, we applied both **z-score standardization** and **min-max scaling** so variables
with different units — dollars, degrees, stock prices — can be compared directly in models.

On the categorical side, we used **threshold classification** to flag high-discount weeks, cold
weather periods, and abnormal return rates. We used **interval binning** to create temperature
bands like Freezing, Cold, Cool, and Warm — based on actual meteorological thresholds. And we
used **quantile binning** to classify Amazon's stock into Bear, Neutral, and Bull market periods.

Finally, we consolidated 10 product categories down to 3 business segments — Performance &
Muscle, General Wellness, and Weight & Recovery — making the analysis more actionable for
decision-makers.

The result: **78 total columns** after transformation, giving us a rich feature set for both
BI and AI analysis."

---

## PERSON 3 — BI Analysis & Key Findings (5:00 – 7:30)

> Navigate to **EDA + Visualizations**, starting on the Revenue Trends tab.

"Now let's look at what the data actually tells us.

Looking at the weekly revenue trend, total sales held relatively steady from 2020 through 2025
with some seasonal variation. The 8-week rolling average smooths out week-to-week noise and
shows a slight upward trend — consistent with overall e-commerce growth post-pandemic.

> Switch to the Weather Impact tab.

On weather — this is where it gets interesting. Revenue is highest in **Summer** and lowest in
**Winter**. Looking at temperature bands, **Cool weeks between 50 and 68 degrees** actually
outperform warmer weeks, suggesting people aren't buying supplements when it's extremely hot
either. Precipitation had virtually no effect, which makes sense — these are online purchases.

> Switch to the Stock Signals tab.

On the market side, Amazon's stock price ranged from $83 to $237 over this period. When we split
weeks into Bear, Neutral, and Bull market bands, **Bull market periods correlate with slightly
higher supplement revenue** — consistent with the idea that consumer confidence drives
discretionary health spending.

> Navigate to the Key Findings page.

Our three headline KPIs: **$22.9 million in total revenue**, a **1.02% return rate** — which is
exceptionally low and signals strong customer satisfaction — and **41% of weeks involved high
discounts of 15% or more**, meaning promotions are a major sales driver.

The top product was **Biotin**, the top segment was **General Wellness**, and **iHerb** edged
out Amazon and Walmart in total revenue — likely due to its specialized supplement-focused
customer base."

---

## PERSON 4 — AI Augmentation & Conclusion (7:30 – 10:00)

> Navigate to the **AI Query Assistant** page.

"The final component of our project is where AI augments the BI process directly — our
**AI Query Assistant**, built using Groq's free API running Llama 3.3 70B.

This fulfills Phase 4 of the project — AI-enabled automation of diagnostic analytics. Instead
of a data analyst having to write Python every time a stakeholder has a question, anyone can
type a plain-English question and get a visualization or table back instantly.

For example — [type into the box]: 'Show total revenue by platform as a bar chart.' The AI
receives the full schema of our 78-column dataset, generates the pandas and Plotly code,
executes it, and renders the result — all in seconds.

This is prescriptive analytics in practice: it lowers the barrier between business questions
and data answers.

> Navigate back to Business Overview briefly.

To wrap up — our project delivered a complete AI-powered BI workflow:
- **3 data sources** integrated into a single 4,384-row dataset
- **11 transformation techniques** applied
- **15+ interactive visualizations** across revenue, weather, and market dimensions
- **An AI assistant** that lets non-technical stakeholders query the data in plain English

Limitations to acknowledge: our weather data comes from a single NOAA station in West Virginia,
which is a proxy for national climate rather than a direct market signal. And the stock data
reflects broad e-commerce sentiment, not supplement-specific consumer behavior.

For future work, we'd recommend expanding to regional weather stations and incorporating actual
search trend data as a demand signal.

Thank you — we're happy to take any questions, and the live dashboard is available for you
to explore."

---

## Tips for Presenting

- Person 4 should have the Groq API key pre-entered before the presentation starts
- Keep the dashboard open in full-screen with the sidebar collapsed during the demo
- Each person navigates to their page when it's their turn — the live dashboard is your slide deck
- Practice the transitions between pages so they feel smooth
- The dashboard URL to open: http://localhost:8501
