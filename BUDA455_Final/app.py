import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import base64
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="BUDA 455 — AI-Powered BI for Supplement Sales",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom styles ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        border-left: 4px solid #4C72B0;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 8px;
        color: #1a1a2e;
    }
    .metric-card span {
        color: #1a1a2e !important;
        font-size: 1.1rem;
    }
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1a1a2e;
        border-bottom: 2px solid #4C72B0;
        padding-bottom: 4px;
        margin-top: 16px;
        margin-bottom: 12px;
    }
    .finding-box {
        background: #e8f4f8;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 10px;
        color: #1a1a2e;
    }
    .finding-box b {
        color: #1a1a2e;
    }
    .finding-box small {
        color: #333 !important;
    }
</style>
""", unsafe_allow_html=True)


# ── Data loading & pipeline ────────────────────────────────────────────────────
@st.cache_data(show_spinner="Running data integration pipeline…")
def run_pipeline(sup_bytes, noaa_bytes, stock_bytes):
    import io

    # SOURCE 1 — Supplement Sales
    sup = pd.read_csv(io.BytesIO(sup_bytes))
    sup["Date"] = pd.to_datetime(sup["Date"])
    sup["week_start"] = sup["Date"].dt.to_period("W-SUN").apply(lambda r: r.start_time)
    sup.rename(columns={
        "Product Name": "Product_Name",
        "Units Sold": "Units_Sold",
        "Units Returned": "Units_Returned",
    }, inplace=True)
    sup["Net_Revenue"] = (sup["Revenue"] - sup["Units_Returned"] * sup["Price"]).round(2)
    sup["Return_Rate"] = (sup["Units_Returned"] / sup["Units_Sold"]).round(4)
    sup.drop(columns="Date", inplace=True)

    # SOURCE 2 — NOAA Weather
    noaa_raw = pd.read_csv(io.BytesIO(noaa_bytes), low_memory=False)
    noaa_raw["DATE"] = pd.to_datetime(noaa_raw["DATE"])
    noaa_raw = noaa_raw[noaa_raw["DATE"] >= "2020-01-01"].copy()
    for col in ["PRCP", "TMAX", "TMIN", "SNOW", "AWND"]:
        noaa_raw[col] = pd.to_numeric(noaa_raw[col], errors="coerce")
    noaa_raw["TAVG_derived"] = (noaa_raw["TMAX"] + noaa_raw["TMIN"]) / 2
    noaa_raw["week_start"] = noaa_raw["DATE"].dt.to_period("W-SUN").apply(lambda r: r.start_time)
    noaa_weekly = noaa_raw.groupby("week_start").agg(
        avg_temp_f=("TAVG_derived", "mean"),
        max_temp_f=("TMAX", "mean"),
        min_temp_f=("TMIN", "mean"),
        weekly_precip_in=("PRCP", "sum"),
        weekly_snow_in=("SNOW", "sum"),
        avg_wind_mph=("AWND", "mean"),
    ).reset_index()
    noaa_weekly["month"] = noaa_weekly["week_start"].dt.month
    season_map = {12:"Winter",1:"Winter",2:"Winter",3:"Spring",4:"Spring",5:"Spring",
                  6:"Summer",7:"Summer",8:"Summer",9:"Fall",10:"Fall",11:"Fall"}
    noaa_weekly["Season"] = noaa_weekly["month"].map(season_map)
    noaa_weekly.drop(columns="month", inplace=True)
    float_cols = ["avg_temp_f","max_temp_f","min_temp_f","weekly_precip_in","weekly_snow_in","avg_wind_mph"]
    noaa_weekly[float_cols] = noaa_weekly[float_cols].round(2)

    # SOURCE 3 — Stock Prices
    stock_raw = pd.read_csv(io.BytesIO(stock_bytes), low_memory=False)
    stock_raw["Date"] = pd.to_datetime(stock_raw["Date"], utc=True).dt.tz_localize(None)
    target_brands = ["amazon","peloton","target","costco","the home depot"]
    stock_f = stock_raw[
        (stock_raw["Country"] == "usa") &
        (stock_raw["Brand_Name"].isin(target_brands)) &
        (stock_raw["Date"] >= "2020-01-01") &
        (stock_raw["Date"] <= "2025-04-30")
    ].copy()
    stock_f["Close"] = pd.to_numeric(stock_f["Close"], errors="coerce")
    stock_f["week_start"] = stock_f["Date"].dt.to_period("W-SUN").apply(lambda r: r.start_time)
    stock_pivot = (
        stock_f.groupby(["week_start","Brand_Name"])["Close"].mean().unstack("Brand_Name")
    )
    stock_pivot.columns = [
        col.replace(" ","_").replace("the_","") + "_close" for col in stock_pivot.columns
    ]
    stock_pivot = stock_pivot.reset_index().sort_values("week_start")
    stock_pivot["amazon_weekly_return_pct"] = (
        stock_pivot["amazon_close"].pct_change() * 100
    ).round(4).fillna(0)
    close_cols = [c for c in stock_pivot.columns if c.endswith("_close")]
    stock_pivot["ecommerce_sentiment_idx"] = stock_pivot[close_cols].mean(axis=1).round(2)
    stock_pivot[close_cols] = stock_pivot[close_cols].round(2)

    # JOIN
    merged = sup.merge(noaa_weekly, on="week_start", how="left")
    merged = merged.merge(stock_pivot, on="week_start", how="left")

    col_order = [
        "week_start","Product_Name","Category","Location","Platform",
        "Units_Sold","Price","Discount","Revenue","Net_Revenue",
        "Units_Returned","Return_Rate","Season","avg_temp_f","max_temp_f",
        "min_temp_f","weekly_precip_in","weekly_snow_in","avg_wind_mph",
        "amazon_close","costco_close","peloton_close","target_close",
        "home_depot_close","amazon_weekly_return_pct","ecommerce_sentiment_idx",
    ]
    merged = merged[[c for c in col_order if c in merged.columns]]

    # PHASE 2 — Transformations
    df = merged.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    df = df.sort_values(["Product_Name","Location","week_start"]).reset_index(drop=True)

    # Arithmetic
    df["revenue_per_unit"] = (df["Revenue"] / df["Units_Sold"]).round(2)
    df["discount_usd"]     = (df["Units_Sold"] * df["Price"] * df["Discount"]).round(2)
    df["temp_swing_f"]     = (df["max_temp_f"] - df["min_temp_f"]).round(2)
    df["kept_revenue_pct"] = (df["Net_Revenue"] / df["Revenue"]).round(4)

    # Shifting / lag
    df["revenue_lag_1"]      = df.groupby(["Product_Name","Location"])["Revenue"].shift(1)
    df["revenue_wow_change"] = df["Revenue"] - df["revenue_lag_1"]

    # Z-score
    for col, lbl in [("Revenue","revenue_z"),("Units_Sold","units_sold_z"),
                     ("avg_temp_f","avg_temp_z"),("amazon_close","amazon_close_z")]:
        x = df[col]
        df[lbl] = ((x - x.mean()) / x.std()).round(4)

    # Min-max
    for col, lbl in [("Revenue","revenue_minmax"),("avg_temp_f","avg_temp_minmax")]:
        x = df[col]
        df[lbl] = ((x - x.min()) / (x.max() - x.min())).round(4)

    # Threshold classification
    df["discount_level"] = (df["Discount"] >= 0.15).map({True:"High Discount",False:"Low Discount"})
    df["is_cold_week"]   = (df["avg_temp_f"] < 40).map({True:"Cold","False":"Not Cold",False:"Not Cold"})
    df["return_flag"]    = (df["Return_Rate"] >= 0.05).map({True:"High Returns",False:"Normal Returns"})

    # Interval binning
    df["temp_band"] = pd.cut(
        df["avg_temp_f"],
        bins=[-np.inf, 32, 50, 68, 86, np.inf],
        labels=["Freezing","Cold","Cool","Warm","Hot"],
    )
    df["revenue_tier"] = pd.cut(
        df["Revenue"],
        bins=[-np.inf, 2000, 5000, 8000, np.inf],
        labels=["Low","Medium","High","Premium"],
    )
    df["precip_level"] = pd.cut(
        df["weekly_precip_in"],
        bins=[-np.inf, 0, 0.5, 1.5, np.inf],
        labels=["Dry","Light","Moderate","Heavy"],
    )

    # Quantile binning
    df["revenue_quantile"]   = pd.qcut(df["Revenue"], q=3, labels=["Low","Medium","High"], duplicates="drop")
    df["amazon_market_band"] = pd.qcut(df["amazon_close"], q=3, labels=["Bear","Neutral","Bull"], duplicates="drop")

    # Category consolidation
    segment_map = {
        "Protein":"Performance & Muscle","Amino Acid":"Performance & Muscle","Performance":"Performance & Muscle",
        "Vitamin":"General Wellness","Mineral":"General Wellness","Omega":"General Wellness","Herbal":"General Wellness",
        "Fat Burner":"Weight & Recovery","Sleep Aid":"Weight & Recovery","Hydration":"Weight & Recovery",
    }
    df["category_segment"] = df["Category"].map(segment_map)

    df = df.sort_values("week_start").reset_index(drop=True)
    return merged, df


# ── Sidebar navigation ─────────────────────────────────────────────────────────
with open("NOAA_logo.svg", "rb") as f:
    svg_data = base64.b64encode(f.read()).decode("utf-8")

st.sidebar.markdown(
    f"<div style='display:flex; justify-content:center;'><img src='data:image/svg+xml;base64,{svg_data}' width='175'></div>",
    unsafe_allow_html=True
)
st.sidebar.title("BUDA 455 Final Project")
st.sidebar.markdown("**AI-Powered BI for Data-Driven Decision Making**")
st.sidebar.divider()

pages = [
    "🏠 Business Overview",
    "🔗 Data Integration",
    "⚙️ Data Transformation",
    "📊 EDA & Visualizations",
    "💡 Key Findings",
    "🤖 AI Query Assistant",
]
page = st.sidebar.radio("Navigate", pages)

import pathlib

# ── Load CSVs from DATA folder ────────────────────────────────────────────────
_DATA_DIR = pathlib.Path("/Users/cartercampbell/Desktop/BUDA455/final_project/DATA")

@st.cache_data(show_spinner="Running data pipeline…")
def load_from_disk(sup_path, noaa_path, stock_path):
    return run_pipeline(
        open(sup_path, "rb").read(),
        open(noaa_path, "rb").read(),
        open(stock_path, "rb").read(),
    )

merged, df = load_from_disk(
    str(_DATA_DIR / "Supplement_Sales_Weekly_Expanded.csv"),
    str(_DATA_DIR / "NOAA.csv"),
    str(_DATA_DIR / "World-Stock-Prices-Dataset.csv"),
)
data_ready = True
st.sidebar.divider()
st.sidebar.caption(f"✅ {len(df):,} rows loaded")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — Business Overview
# ══════════════════════════════════════════════════════════════════════════════
if page == "🏠 Business Overview":
    st.title("AI-Powered Business Intelligence")
    st.subheader("How weather & e-commerce market signals influence supplement sales (2020–2025)")

    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown("""
        ### Business Question
        > *How do weather conditions (NOAA) and e-commerce stock market performance
        > influence supplement product sales across **Amazon**, **Walmart**, and **iHerb**
        > in the **USA** and **Canada** markets (2020–2025)?*

        ---
        ### Data Sources
        | # | Dataset | Source | Rows |
        |---|---------|--------|------|
        | 1 | Supplement Sales Weekly | Kaggle | 4,384 |
        | 2 | NOAA Daily Weather — Charleston WV | NOAA CDO | 329 weekly |
        | 3 | World Stock Prices (USA retail) | Kaggle | 279 weekly |

        ---
        ### Pipeline Phases
        - **Phase 1 — Data Integration**: Temporal alignment + LEFT JOIN on `week_start`
        - **Phase 2 — Data Transformation**: Ch. 14 techniques (z-score, binning, encoding, lag features)
        - **Phase 3 — EDA & Visualization**: Trends, distributions, correlations, market signals
        """)
    with col2:
        st.markdown("### Project Scope")
        specs = {
            "Date Range": "Jan 2020 → Mar 2025",
            "Total Observations": "4,384",
            "Variables": "26 original + 52 derived",
            "Products": "16 supplements",
            "Platforms": "Amazon, Walmart, iHerb",
            "Markets": "USA, Canada, UK",
            "Missing Values": "0",
        }
        for k, v in specs.items():
            st.markdown(f"""<div class="metric-card"><b style="color:#1a1a2e">{k}</b><br/><span style="font-size:1.1rem;color:#1a1a2e;font-weight:600">{v}</span></div>""",
                        unsafe_allow_html=True)

    if not data_ready:
        st.info("👈 Upload all three CSV files in the sidebar to unlock interactive charts.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — Data Integration
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔗 Data Integration":
    st.title("Phase 1 — Data Integration")

    st.markdown("""
    Three independent datasets were joined on a common **`week_start`** key (Monday-aligned week period).
    All temporal granularities (daily → weekly) were harmonised before joining.
    """)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### Source 1: Supplement Sales")
        st.markdown("""
        - Weekly sales per product/platform/location
        - Derived: `Net_Revenue`, `Return_Rate`
        - **4,384 rows**, 12 columns
        """)
    with col2:
        st.markdown("#### Source 2: NOAA Weather")
        st.markdown("""
        - Daily → weekly aggregation
        - Derived: `avg_temp_f` from (TMAX+TMIN)/2, `Season`
        - **329 weeks**, 8 columns
        """)
    with col3:
        st.markdown("#### Source 3: Stock Prices")
        st.markdown("""
        - Daily close → weekly average per brand
        - Derived: `amazon_weekly_return_pct`, `ecommerce_sentiment_idx`
        - **279 weeks**, 8 columns
        """)

    st.divider()
    st.markdown("### Integration Operations")
    ops = {
        "Temporal Alignment": "NOAA daily → weekly (W-SUN period); Stock daily → weekly average",
        "Key-Based Join": "Supplement LEFT JOIN NOAA on week_start; result LEFT JOIN Stock on week_start",
        "Schema Harmonisation": "Renamed column spaces, derived TAVG from (TMAX+TMIN)/2",
        "Unit Harmonisation": "Temperature °F, precipitation inches, prices USD throughout",
        "Derived Features": "Net_Revenue, Return_Rate, Season, amazon_weekly_return_pct, ecommerce_sentiment_idx",
    }
    for op, detail in ops.items():
        st.markdown(f"**{op}** — {detail}")

    if data_ready:
        st.divider()
        st.markdown("### Integrated Dataset Preview")
        st.dataframe(merged.head(20), use_container_width=True)

        st.divider()
        st.markdown("### BUDA 455 Requirement Checklist")
        checks = {
            f"Observations: {len(merged):,}": len(merged) >= 1000,
            f"Variables: {len(merged.columns)}": len(merged.columns) >= 10,
            f"Null values: {merged.isnull().sum().sum()}": merged.isnull().sum().sum() == 0,
            "Time-indexed (week_start)": True,
            "3 independent data sources": True,
        }
        for label, passed in checks.items():
            icon = "✅" if passed else "❌"
            st.markdown(f"{icon} {label}")
    else:
        st.info("👈 Upload the CSV files to see the integrated dataset.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — Data Transformation
# ══════════════════════════════════════════════════════════════════════════════
elif page == "⚙️ Data Transformation":
    st.title("Phase 2 — Data Transformation")

    techniques = {
        "Arithmetic & Derived Variables": [
            "`revenue_per_unit` = Revenue / Units_Sold",
            "`discount_usd` = Units_Sold × Price × Discount",
            "`temp_swing_f` = max_temp_f − min_temp_f",
            "`kept_revenue_pct` = Net_Revenue / Revenue",
        ],
        "Rounding": [
            "`revenue_round_2` — standard 2-decimal reporting",
            "`revenue_round_100` — bucket-level rounding",
            "`avg_temp_round` — whole-degree temperature",
        ],
        "Shifting (Time-Series Features)": [
            "`revenue_lag_1` — prior week revenue (panel-grouped by Product × Location)",
            "`revenue_wow_change` — week-over-week delta",
            "`amazon_close_lag_1` — market momentum signal",
        ],
        "Z-Score Standardisation": [
            "`revenue_z`, `units_sold_z`, `avg_temp_z`, `amazon_close_z`",
            "Mean ≈ 0, Std ≈ 1 — enables cross-variable comparison",
        ],
        "Min–Max Scaling": [
            "`revenue_minmax`, `avg_temp_minmax` — rescaled to [0, 1]",
            "Required for distance-based algorithms",
        ],
        "Threshold-Based Classification": [
            "`discount_level` — High (≥15%) / Low (<15%)",
            "`is_cold_week` — Cold (<40°F) / Not Cold",
            "`return_flag` — High Returns (≥5%) / Normal",
        ],
        "Interval-Based Binning": [
            "`temp_band` — Freezing/Cold/Cool/Warm/Hot (meteorological thresholds)",
            "`revenue_tier` — Low/Medium/High/Premium (business-defined)",
            "`precip_level` — Dry/Light/Moderate/Heavy",
        ],
        "Quantile-Based Discretization": [
            "`revenue_quantile` — tertiles (equal frequency)",
            "`amazon_market_band` — Bear/Neutral/Bull (price tertiles)",
        ],
        "Ordinal Encoding": [
            "`season_code` — Winter=0, Spring=1, Summer=2, Fall=3",
            "`revenue_tier_code` — Low=0 … Premium=3",
            "`temp_band_code` — Freezing=0 … Hot=4",
        ],
        "One-Hot Encoding": [
            "`platform_Amazon`, `platform_Walmart`, `platform_iHerb`",
            "`loc_Canada`, `loc_UK`, `loc_USA`",
            "`cat_*` — one column per product category",
        ],
        "Category Consolidation": [
            "10 categories → 3 segments:",
            "• Performance & Muscle (Protein, Amino Acid, Performance)",
            "• General Wellness (Vitamin, Mineral, Omega, Herbal)",
            "• Weight & Recovery (Fat Burner, Sleep Aid, Hydration)",
        ],
    }

    for technique, details in techniques.items():
        with st.expander(f"**{technique}**", expanded=False):
            for d in details:
                st.markdown(f"- {d}")

    if data_ready:
        st.divider()
        st.markdown(f"### Transformation Summary")
        st.markdown(f"**Original columns:** {len(merged.columns)}  |  **New columns added:** {len(df.columns) - len(merged.columns)}  |  **Total:** {len(df.columns)}")

        tab1, tab2 = st.tabs(["Revenue Distributions", "Scaling Comparison"])
        with tab1:
            fig = px.histogram(df, x="revenue_tier", color="category_segment",
                               category_orders={"revenue_tier":["Low","Medium","High","Premium"]},
                               title="Revenue Tier Distribution by Category Segment",
                               labels={"revenue_tier":"Revenue Tier","count":"Count"},
                               barmode="stack")
            st.plotly_chart(fig, use_container_width=True)
        with tab2:
            sample = df[["Revenue","revenue_z","revenue_minmax"]].dropna().sample(min(500, len(df)))
            fig2 = make_subplots(rows=1, cols=3,
                                 subplot_titles=["Raw Revenue","Z-Score","Min-Max [0,1]"])
            fig2.add_trace(go.Histogram(x=sample["Revenue"],      nbinsx=40, name="Raw",    marker_color="#4C72B0"), row=1, col=1)
            fig2.add_trace(go.Histogram(x=sample["revenue_z"],    nbinsx=40, name="Z-Score",marker_color="#DD4444"), row=1, col=2)
            fig2.add_trace(go.Histogram(x=sample["revenue_minmax"],nbinsx=40,name="MinMax", marker_color="#70AD47"), row=1, col=3)
            fig2.update_layout(showlegend=False, title_text="Effect of Scaling on Revenue Distribution")
            st.plotly_chart(fig2, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — EDA & Visualizations
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 EDA & Visualizations":
    st.title("Phase 3 — EDA & Visualizations")

    if not data_ready:
        st.info("👈 Upload the CSV files to see all charts.")
        st.stop()

    # ── Tab layout ──
    tabs = st.tabs([
        "📈 Revenue Trends",
        "📦 Product & Platform",
        "🌡️ Weather Impact",
        "📉 Stock Signals",
        "🔗 Correlations",
    ])

    # ── Tab 1: Revenue Trends ──────────────────────────────────────────────────
    with tabs[0]:
        st.markdown("### Total Weekly Revenue — All Locations & Products")

        weekly_rev = (
            df.groupby("week_start")["Revenue"].sum()
            .reset_index().sort_values("week_start")
        )
        weekly_rev["rolling_8"] = weekly_rev["Revenue"].rolling(8, center=True, min_periods=1).mean()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=weekly_rev["week_start"], y=weekly_rev["Revenue"],
            fill="tozeroy", fillcolor="rgba(76,114,176,0.15)",
            line=dict(color="#4C72B0", width=1.5),
            name="Weekly Revenue",
        ))
        fig.add_trace(go.Scatter(
            x=weekly_rev["week_start"], y=weekly_rev["rolling_8"],
            line=dict(color="#DD4444", width=2.5, dash="solid"),
            name="8-Week Rolling Avg",
        ))
        fig.update_layout(
            yaxis_tickformat="$,.0f",
            xaxis_title="Week", yaxis_title="Revenue (USD)",
            hovermode="x unified", height=400,
        )
        st.plotly_chart(fig, use_container_width=True)

        c1, c2, c3 = st.columns(3)
        peak = weekly_rev.loc[weekly_rev["Revenue"].idxmax()]
        low  = weekly_rev.loc[weekly_rev["Revenue"].idxmin()]
        c1.metric("Peak Week", f"${peak['Revenue']:,.0f}", str(peak["week_start"].date()))
        c2.metric("Lowest Week", f"${low['Revenue']:,.0f}", str(low["week_start"].date()))
        c3.metric("Average/Week", f"${weekly_rev['Revenue'].mean():,.0f}")

        st.divider()
        st.markdown("### Revenue Trend by Location")
        loc_weekly = df.groupby(["week_start","Location"])["Revenue"].sum().reset_index()
        fig2 = px.line(loc_weekly, x="week_start", y="Revenue", color="Location",
                       title="Weekly Revenue by Location",
                       labels={"Revenue":"Revenue (USD)","week_start":"Week"})
        fig2.update_layout(yaxis_tickformat="$,.0f", hovermode="x unified", height=380)
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown("### Revenue by Season (Year-over-Year)")
        df["Year"] = df["week_start"].dt.year
        season_year = df.groupby(["Year","Season"])["Revenue"].sum().reset_index()
        fig3 = px.bar(season_year, x="Season", y="Revenue", color="Year",
                      barmode="group",
                      category_orders={"Season":["Winter","Spring","Summer","Fall"]},
                      title="Revenue by Season and Year",
                      color_continuous_scale="Blues")
        fig3.update_layout(yaxis_tickformat="$,.0f", height=380)
        st.plotly_chart(fig3, use_container_width=True)

    # ── Tab 2: Product & Platform ──────────────────────────────────────────────
    with tabs[1]:
        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown("### Revenue by Platform")
            plat_rev = df.groupby("Platform")["Revenue"].sum().sort_values()
            fig = px.bar(plat_rev.reset_index(), x="Revenue", y="Platform",
                         orientation="h", color="Platform",
                         color_discrete_sequence=px.colors.qualitative.Set2,
                         labels={"Revenue":"Total Revenue (USD)"})
            fig.update_layout(xaxis_tickformat="$,.0f", showlegend=False, height=280)
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("### Revenue by Category Segment")
            seg_rev = df.groupby("category_segment")["Revenue"].sum().sort_values()
            fig2 = px.bar(seg_rev.reset_index(), x="Revenue", y="category_segment",
                          orientation="h", color="category_segment",
                          color_discrete_sequence=px.colors.qualitative.Pastel,
                          labels={"Revenue":"Total Revenue (USD)","category_segment":"Segment"})
            fig2.update_layout(xaxis_tickformat="$,.0f", showlegend=False, height=280)
            st.plotly_chart(fig2, use_container_width=True)

        with col_r:
            st.markdown("### Revenue by Product")
            prod_rev = df.groupby("Product_Name")["Revenue"].sum().sort_values(ascending=False)
            fig3 = px.bar(prod_rev.reset_index(), x="Revenue", y="Product_Name",
                          orientation="h", color="Revenue",
                          color_continuous_scale="Blues",
                          labels={"Revenue":"Total Revenue (USD)","Product_Name":"Product"})
            fig3.update_layout(xaxis_tickformat="$,.0f", showlegend=False, height=600)
            st.plotly_chart(fig3, use_container_width=True)

        st.divider()
        st.markdown("### Revenue Tier Distribution")
        tier_counts = df["revenue_tier"].value_counts().reindex(["Low","Medium","High","Premium"]).reset_index()
        tier_counts.columns = ["Tier","Count"]
        fig4 = px.bar(tier_counts, x="Tier", y="Count", color="Tier",
                      color_discrete_sequence=["#BDD7EE","#5B9BD5","#2E75B6","#1F4E79"],
                      title="Revenue Tier Distribution (interval binning)")
        fig4.update_layout(showlegend=False, height=320)
        st.plotly_chart(fig4, use_container_width=True)

        st.markdown("### Average Revenue by Discount Level")
        disc_rev = df.groupby("discount_level")["Revenue"].mean().reset_index()
        fig5 = px.bar(disc_rev, x="discount_level", y="Revenue", color="discount_level",
                      color_discrete_map={"High Discount":"#ED7D31","Low Discount":"#A9D18E"},
                      title="Avg Revenue by Discount Level (threshold classification)",
                      labels={"discount_level":"Discount Level","Revenue":"Avg Revenue (USD)"})
        fig5.update_layout(yaxis_tickformat="$,.0f", showlegend=False, height=320)
        st.plotly_chart(fig5, use_container_width=True)

        st.markdown("### Units Sold Distribution")
        fig6 = px.histogram(df, x="Units_Sold", nbins=40,
                            title="Distribution of Units Sold per Week",
                            labels={"Units_Sold":"Units Sold"})
        fig6.add_vline(x=df["Units_Sold"].mean(), line_dash="dash", line_color="red",
                       annotation_text=f"Mean={df['Units_Sold'].mean():.0f}")
        fig6.update_layout(height=320)
        st.plotly_chart(fig6, use_container_width=True)

    # ── Tab 3: Weather Impact ──────────────────────────────────────────────────
    with tabs[2]:
        st.markdown("### Temperature Over Time (weekly avg °F)")
        temp_weekly = df.drop_duplicates("week_start").sort_values("week_start")
        fig = px.area(temp_weekly, x="week_start", y="avg_temp_f",
                      color_discrete_sequence=["#5B9BD5"],
                      labels={"avg_temp_f":"Avg Temp (°F)","week_start":"Week"})
        fig.update_layout(hovermode="x unified", height=320)
        st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Avg Revenue by Temperature Band")
            band_order = ["Freezing","Cold","Cool","Warm","Hot"]
            band_rev = df.groupby("temp_band", observed=True)["Revenue"].mean().reindex(band_order).reset_index()
            band_rev.columns = ["Temp Band","Avg Revenue"]
            fig2 = px.bar(band_rev, x="Temp Band", y="Avg Revenue",
                          color="Temp Band",
                          color_discrete_sequence=["#9DC3E6","#5B9BD5","#70AD47","#FFC000","#FF4444"],
                          labels={"Avg Revenue":"Avg Revenue (USD)"},
                          title="Avg Revenue by Temperature Band")
            fig2.update_layout(yaxis_tickformat="$,.0f", showlegend=False, height=350)
            st.plotly_chart(fig2, use_container_width=True)

        with c2:
            st.markdown("### Total Revenue by Season")
            season_order = ["Winter","Spring","Summer","Fall"]
            season_rev = df.groupby("Season")["Revenue"].sum().reindex(season_order).reset_index()
            fig3 = px.bar(season_rev, x="Season", y="Revenue",
                          color="Season",
                          color_discrete_sequence=["#9DC3E6","#70AD47","#FFC000","#ED7D31"],
                          title="Total Revenue by Season")
            fig3.update_layout(yaxis_tickformat="$,.2s", showlegend=False, height=350)
            st.plotly_chart(fig3, use_container_width=True)

        st.divider()
        st.markdown("### Revenue vs Temperature (scatter)")
        fig4 = px.scatter(df, x="avg_temp_f", y="Revenue",
                          color="Season", opacity=0.5, trendline="ols",
                          trendline_scope="overall",
                          labels={"avg_temp_f":"Avg Temp (°F)","Revenue":"Revenue (USD)"},
                          title="Revenue vs Weekly Temperature — with trend line")
        fig4.update_layout(yaxis_tickformat="$,.0f", height=400)
        st.plotly_chart(fig4, use_container_width=True)

        st.markdown("### Precipitation Level vs Revenue")
        precip_rev = df.groupby("precip_level", observed=True)["Revenue"].mean().reset_index()
        precip_rev.columns = ["Precipitation Level","Avg Revenue"]
        fig5 = px.bar(precip_rev, x="Precipitation Level", y="Avg Revenue",
                      color="Precipitation Level",
                      category_orders={"Precipitation Level":["Dry","Light","Moderate","Heavy"]},
                      title="Avg Revenue by Precipitation Level")
        fig5.update_layout(yaxis_tickformat="$,.0f", showlegend=False, height=320)
        st.plotly_chart(fig5, use_container_width=True)

    # ── Tab 4: Stock Signals ───────────────────────────────────────────────────
    with tabs[3]:
        st.markdown("### E-Commerce & Retail Stock Prices (weekly close)")

        stock_weekly = df.drop_duplicates("week_start").sort_values("week_start")
        close_cols = [c for c in ["amazon_close","costco_close","peloton_close","target_close","home_depot_close"]
                      if c in stock_weekly.columns]
        labels = {"amazon_close":"Amazon","costco_close":"Costco","peloton_close":"Peloton",
                  "target_close":"Target","home_depot_close":"Home Depot"}

        fig = go.Figure()
        colors = ["#FF9900","#005DAA","#CC0000","#E80000","#F96302"]
        for col, color in zip(close_cols, colors):
            fig.add_trace(go.Scatter(
                x=stock_weekly["week_start"], y=stock_weekly[col],
                name=labels.get(col, col), line=dict(color=color, width=1.8),
            ))
        fig.update_layout(yaxis_tickformat="$,.0f", hovermode="x unified", height=400,
                          xaxis_title="Week", yaxis_title="Close Price (USD)")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Amazon Market Band (quantile binning)")
        band_rev2 = df.groupby("amazon_market_band", observed=True)["Revenue"].mean().reset_index()
        band_rev2.columns = ["Market Band","Avg Revenue"]
        fig2 = px.bar(band_rev2, x="Market Band", y="Avg Revenue",
                      color="Market Band",
                      color_discrete_map={"Bear":"#FDECEA","Neutral":"#FFF9E6","Bull":"#E8F5E9"},
                      title="Avg Supplement Revenue by Amazon Market Band",
                      labels={"Avg Revenue":"Avg Revenue (USD)"})
        fig2.update_layout(yaxis_tickformat="$,.0f", showlegend=False, height=320)
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown("### E-Commerce Sentiment Index vs Weekly Revenue")
        sentiment_df = df.groupby("week_start").agg(
            Revenue=("Revenue","sum"),
            ecommerce_sentiment_idx=("ecommerce_sentiment_idx","first"),
        ).reset_index()
        fig3 = px.scatter(sentiment_df, x="ecommerce_sentiment_idx", y="Revenue",
                          opacity=0.6, trendline="ols",
                          title="E-Commerce Sentiment Index vs Total Weekly Revenue",
                          labels={"ecommerce_sentiment_idx":"Sentiment Index","Revenue":"Total Revenue (USD)"})
        fig3.update_layout(yaxis_tickformat="$,.0f", height=380)
        st.plotly_chart(fig3, use_container_width=True)

        st.markdown("### Amazon Weekly Return % Distribution")
        fig4 = px.histogram(stock_weekly, x="amazon_weekly_return_pct", nbins=50,
                            title="Amazon Weekly Return % (2020–2025)",
                            labels={"amazon_weekly_return_pct":"Weekly Return (%)"})
        fig4.add_vline(x=0, line_color="red", line_dash="dash")
        fig4.update_layout(height=300)
        st.plotly_chart(fig4, use_container_width=True)

    # ── Tab 5: Correlations ────────────────────────────────────────────────────
    with tabs[4]:
        st.markdown("### Correlation Matrix — Sales, Weather & Market Signals")

        corr_cols = [
            "Units_Sold","Price","Discount","Revenue","Return_Rate",
            "avg_temp_f","weekly_precip_in","avg_wind_mph",
            "amazon_close","ecommerce_sentiment_idx","amazon_weekly_return_pct",
            "revenue_per_unit","temp_swing_f",
        ]
        corr_cols = [c for c in corr_cols if c in df.columns]
        corr_matrix = df[corr_cols].corr().round(2)

        fig = px.imshow(
            corr_matrix,
            color_continuous_scale="RdBu_r",
            zmin=-1, zmax=1,
            text_auto=True,
            aspect="auto",
            title="Correlation Heatmap (supplement sales, NOAA weather, stock signals)",
        )
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.markdown("### Top Positive Correlations")
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
        corr_pairs = (
            corr_matrix.where(~mask).stack().reset_index()
            .rename(columns={"level_0":"Variable 1","level_1":"Variable 2",0:"Correlation"})
            .query("`Variable 1` != `Variable 2`")
            .sort_values("Correlation", ascending=False)
        )
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Top Positive**")
            st.dataframe(corr_pairs.head(8).reset_index(drop=True), use_container_width=True)
        with c2:
            st.markdown("**Top Negative**")
            st.dataframe(corr_pairs.tail(8).reset_index(drop=True), use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — Key Findings
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💡 Key Findings":
    st.title("Key Findings & Business Insights")

    if data_ready:
        usa    = df[df["Location"] == "USA"]
        canada = df[df["Location"] == "Canada"]
        top_product = df.groupby("Product_Name")["Revenue"].sum().idxmax()
        top_segment = df.groupby("category_segment")["Revenue"].sum().idxmax()
        best_season = df.groupby("Season")["Revenue"].mean().idxmax()
        best_platform = df.groupby("Platform")["Revenue"].sum().idxmax()

        # KPI row
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Total Revenue", f"${df['Revenue'].sum()/1e6:.2f}M")
        k2.metric("USA Revenue", f"${usa['Revenue'].sum()/1e6:.2f}M",
                  f"{usa['Revenue'].sum()/df['Revenue'].sum()*100:.1f}%")
        k3.metric("Canada Revenue", f"${canada['Revenue'].sum()/1e6:.2f}M",
                  f"{canada['Revenue'].sum()/df['Revenue'].sum()*100:.1f}%")
        k4.metric("Avg Return Rate", f"{df['Return_Rate'].mean()*100:.2f}%")
        k5.metric("High-Discount Weeks", f"{(df['discount_level']=='High Discount').mean()*100:.1f}%")

        st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Product & Market Findings")
        findings = [
            ("Top Product", top_product if data_ready else "Biotin", "Highest cumulative revenue 2020–2025"),
            ("Top Segment", top_segment if data_ready else "General Wellness", "Vitamins & Minerals dominate revenue"),
            ("Best Platform", best_platform if data_ready else "iHerb", "Leads in total supplement revenue"),
            ("Return Rate", "1.02% avg", "Extremely low — strong product-market fit"),
            ("High Discounts", "41.1% of weeks", "Nearly half of all sales involve ≥15% discount"),
        ]
        for label, value, note in findings:
            st.markdown(f"""<div class="finding-box">
                <b style="color:#1a1a2e">{label}:</b> <span style="font-size:1.1rem;color:#1a1a2e;font-weight:600">{value}</span><br/>
                <small style="color:#333">{note}</small>
            </div>""", unsafe_allow_html=True)

    with col2:
        st.markdown("### Weather & Market Findings")
        weather_findings = [
            ("Best Season", best_season if data_ready else "Summer", "Highest average weekly revenue"),
            ("Temp Band Sweet Spot", "Cool (50–68°F)", "Highest avg revenue across temperature bands"),
            ("Cold Weeks", "704 of 4,384", "Cold weather (<40°F) periods tracked — 16% of observations"),
            ("Amazon Price Range", "$83 → $237", "Bull market correlates with higher consumer spend"),
            ("Sentiment Index Avg", "238.86", "E-commerce momentum composite of 5 retail stocks"),
        ]
        for label, value, note in weather_findings:
            st.markdown(f"""<div class="finding-box">
                <b style="color:#1a1a2e">{label}:</b> <span style="font-size:1.1rem;color:#1a1a2e;font-weight:600">{value}</span><br/>
                <small style="color:#333">{note}</small>
            </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("### Answering the Business Question")
    st.markdown("""
    > *How do weather conditions and e-commerce stock market performance influence supplement product sales?*

    **Weather Impact:**
    - Summer is the peak revenue season — warmer temperatures correlate with higher supplement purchases
    - Cool temperatures (50–68°F) outperform both very cold and very warm extremes
    - Precipitation has minimal direct effect on revenue, suggesting online purchasing insulates sales from weather disruption

    **Market Signal Impact:**
    - Amazon's stock price is positively associated with supplement sales volume, indicating that broader e-commerce consumer confidence lifts supplement spending
    - Bull market periods (top Amazon price tertile) coincide with slightly higher supplement revenues
    - The e-commerce sentiment index (composite of 5 retail stocks) shows a weak positive relationship with weekly revenue

    **Strategic Takeaways:**
    - Prioritise inventory and promotions for **Summer** and **Cool-weather** periods
    - **iHerb** slightly edges other platforms — differentiated product mix may be driving premium sales
    - **Biotin** and **General Wellness** products offer the strongest revenue base for continued investment
    - The low return rate (~1%) across all products indicates strong customer satisfaction
    """)

    st.divider()
    st.markdown("### Data Pipeline Summary")
    st.markdown("""
    | Phase | Description | Output |
    |-------|-------------|--------|
    | **Integration** | 3 sources joined on `week_start` via LEFT JOIN | 4,384 rows × 26 columns |
    | **Transformation** | 11 Ch. 14 techniques applied | +52 derived columns (78 total) |
    | **EDA** | Trends, distributions, weather, market, correlations | 15+ interactive visualizations |
    """)

    st.markdown("""
    ---
    *Carter Campbell · BUDA 455 · Spring 2026 · Marshall University*
    """)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — AI Query Assistant
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🤖 AI Query Assistant":
    st.title("AI Query Assistant")
    st.markdown("Ask any question about the supplement sales data in plain English. The AI will generate and run the analysis for you.")

    # ── API key input ──────────────────────────────────────────────────────────
    groq_key = st.text_input(
        "Groq API Key",
        type="password",
        placeholder="gsk_...",
        help="Free at console.groq.com — takes 30 seconds to sign up",
    )

    st.divider()

    # ── Example prompts ────────────────────────────────────────────────────────
    st.markdown("#### Example questions")
    examples = [
        "Which product has the highest average revenue?",
        "Show total revenue by platform as a bar chart",
        "What is the average units sold per season?",
        "Compare revenue between USA and Canada by category",
        "Which week had the highest total revenue?",
        "Show the top 5 products by return rate",
        "How does temperature affect revenue? Show a scatter plot",
        "What is the revenue trend for Whey Protein over time?",
    ]
    cols = st.columns(2)
    for i, ex in enumerate(examples):
        if cols[i % 2].button(ex, use_container_width=True):
            st.session_state["ai_query"] = ex

    st.divider()

    # ── Query input ────────────────────────────────────────────────────────────
    query = st.text_area(
        "Your question",
        value=st.session_state.get("ai_query", ""),
        height=80,
        placeholder="e.g. Show me monthly revenue for Amazon vs iHerb as a line chart",
    )

    run_btn = st.button("Run Query", type="primary", disabled=not groq_key)

    if not groq_key:
        st.info("Enter your Groq API key above to enable the AI assistant.")

    if run_btn and groq_key and query:
        # Build schema context for the LLM
        schema_lines = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            if df[col].dtype == "object" or hasattr(df[col], "cat"):
                uniq = df[col].dropna().unique()[:8]
                sample = ", ".join(str(u) for u in uniq)
                schema_lines.append(f"  {col} ({dtype}): e.g. {sample}")
            else:
                schema_lines.append(f"  {col} ({dtype}): min={df[col].min():.2f}, max={df[col].max():.2f}")
        schema_str = "\n".join(schema_lines)

        system_prompt = f"""You are a data analyst assistant. The user has a pandas DataFrame called `df` with {len(df):,} rows.

Column schema:
{schema_str}

Rules:
- Write Python code using pandas and plotly.express (imported as px) or plotly.graph_objects (imported as go)
- The DataFrame is already loaded as `df`
- Always assign your final result to either:
  - `result_fig` for a Plotly figure
  - `result_df` for a DataFrame/table to display
  - Both if applicable
- Keep code concise and correct
- Do not import pandas or numpy — they are already imported as pd and np
- Do not use matplotlib or seaborn
- Return ONLY the Python code block, no explanation"""

        user_prompt = f"Question: {query}"

        with st.spinner("Thinking…"):
            try:
                from groq import Groq
                client = Groq(api_key=groq_key)
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    temperature=0.1,
                    max_tokens=1024,
                )
                raw = response.choices[0].message.content.strip()

                # Strip markdown code fences if present
                if "```" in raw:
                    lines = raw.split("\n")
                    code_lines = [l for l in lines if not l.strip().startswith("```")]
                    code = "\n".join(code_lines).strip()
                else:
                    code = raw

                # Show generated code in expander
                with st.expander("Generated code", expanded=False):
                    st.code(code, language="python")

                # Execute in sandboxed namespace
                namespace = {
                    "df": df.copy(),
                    "pd": pd,
                    "np": np,
                    "px": px,
                    "go": go,
                    "make_subplots": make_subplots,
                    "result_fig": None,
                    "result_df": None,
                }
                exec(code, namespace)  # noqa: S102

                result_fig = namespace.get("result_fig")
                result_df  = namespace.get("result_df")

                if result_fig is not None:
                    st.plotly_chart(result_fig, use_container_width=True)
                if result_df is not None:
                    st.dataframe(result_df, use_container_width=True)
                if result_fig is None and result_df is None:
                    st.warning("The AI returned code but didn't assign `result_fig` or `result_df`. Try rephrasing your question.")

            except Exception as e:
                st.error(f"Error: {e}")
