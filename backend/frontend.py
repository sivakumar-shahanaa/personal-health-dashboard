import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import os
import hashlib
import altair as alt
from dotenv import load_dotenv

from insights import compute_metric_stats, compute_cycle_correlation, generate_insight

load_dotenv()

st.set_page_config(layout="wide", page_title="Biometric Cycle Optimizer", page_icon="🌿")

DB_PATH = os.path.join(os.path.dirname(__file__), "analytics.db")

METRIC_LABEL_TO_DB = {
    "Heart Rate Variability (HRV - ms)": "HRV",
    "Resting Heart Rate (RHR - bpm)": "Resting Heart Rate",
    "Sleep Quality Index (%)": "Sleep Quality Index",
    "Activity (Steps)": "Steps",
}

# ---------------------------------------------------------------------------
# DESIGN TOKENS
# ---------------------------------------------------------------------------
FOREST = "#0F2E22"
MOSS = "#2D5A3D"
SAGE = "#8FAE8B"
BONE = "#F6F7F1"
GOLD = "#D9A441"
BRICK = "#B5563C"
INK = "#1B231D"

# ---------------------------------------------------------------------------
# GLOBAL STYLE INJECTION
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    color: {INK};
}}

.stApp {{
    background-color: {BONE};
}}

.block-container {{
    padding-top: 1.5rem;
    max-width: 1100px;
}}

/* ---- Hero header ---- */
.bco-hero {{
    background: linear-gradient(135deg, {FOREST} 0%, #163D2C 100%);
    border-radius: 16px;
    padding: 2.6rem 2.4rem 2.2rem 2.4rem;
    margin-bottom: 1.6rem;
    position: relative;
    overflow: hidden;
}}
.bco-hero::before {{
    content: "";
    position: absolute;
    inset: 0;
    opacity: 0.16;
    background-image:
        url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 600 200' preserveAspectRatio='none'><path d='M0,140 C80,100 130,180 220,120 C300,70 360,160 460,110 C520,80 560,130 600,100' stroke='%238FAE8B' stroke-width='2' fill='none'/><path d='M0,170 C90,140 150,190 240,150 C320,110 380,180 480,140 C540,115 570,150 600,135' stroke='%238FAE8B' stroke-width='1.4' fill='none'/><path d='M0,60 C70,30 140,70 220,40 C300,10 370,55 460,30 C520,12 560,40 600,25' stroke='%232D5A3D' stroke-width='1.6' fill='none'/></svg>");
    background-size: cover;
}}
.bco-hero-title {{
    font-family: 'Fraunces', serif;
    font-weight: 500;
    font-size: 2.5rem;
    color: {BONE};
    margin: 0 0 0.4rem 0;
    position: relative;
    letter-spacing: -0.02em;
}}
.bco-hero-sub {{
    color: {SAGE};
    font-size: 1.0rem;
    max-width: 640px;
    position: relative;
    line-height: 1.5;
}}
.bco-eyebrow {{
    font-family: 'IBM Plex Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.72rem;
    color: {SAGE};
    position: relative;
    margin-bottom: 0.6rem;
    display: block;
}}

/* ---- Section headers ---- */
h2, h3 {{
    font-family: 'Fraunces', serif;
    font-weight: 500;
    color: {FOREST};
}}

/* ---- Cards (bordered containers) ---- */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: white;
    border: 1px solid #E1E6D9 !important;
    border-radius: 14px !important;
    box-shadow: 0 2px 14px rgba(15, 46, 34, 0.06);
}}
div[data-testid="stVerticalBlockBorderWrapper"] > div {{
    padding: 0.4rem 0.2rem;
}}

/* ---- Metrics ---- */
div[data-testid="stMetric"] {{
    background: {BONE};
    border-radius: 10px;
    padding: 0.8rem 1rem;
    border-left: 3px solid {MOSS};
}}
div[data-testid="stMetricLabel"] {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: {MOSS};
}}
div[data-testid="stMetricValue"] {{
    font-family: 'Fraunces', serif;
    color: {FOREST};
}}

/* ---- Selectbox ---- */
div[data-baseweb="select"] > div {{
    border-radius: 8px !important;
    border-color: {SAGE} !important;
}}

/* ---- Alerts (insight boxes) ---- */
div[data-testid="stAlert"] {{
    border-radius: 10px;
    font-size: 0.95rem;
}}

/* ---- Caption ---- */
[data-testid="stCaptionContainer"] {{
    font-family: 'IBM Plex Mono', monospace;
    color: {MOSS} !important;
}}
</style>
""", unsafe_allow_html=True)


def render_hero():
    st.markdown(f"""
    <div class="bco-hero" style="text-align: center; width: 100%;">
        <span class="bco-eyebrow">Biometric &middot; Cycle &middot; Recovery</span>
        <div class="bco-hero-title" style="margin-top: 10px; font-weight: bold;">Personal Health Data Dashboard</div>
        <div class="bco-hero-sub" style="margin-top: 10px; max-width: 600px; margin-left: auto; margin-right: auto;">
            Track cross-metric correlations, detect phase variances, and surface
            behavioral sleep and recovery insights from your own data.
        </div>
    </div>
    """, unsafe_allow_html=True)


def gradient_bar_chart(df: pd.DataFrame, value_col: str, title: str, color_dark: str, color_light: str):
    """Bar chart with a vertical gradient fill, plus soft area shading underneath."""
    gradient = alt.Gradient(
        gradient="linear",
        stops=[
            alt.GradientStop(color=color_light, offset=0),
            alt.GradientStop(color=color_dark, offset=1),
        ],
        x1=1, x2=1, y1=1, y2=0,
    )

    bars = alt.Chart(df).mark_bar(
        color=gradient, cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=14
    ).encode(
        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %d", grid=False)),
        y=alt.Y(f"{value_col}:Q", title=title, axis=alt.Axis(grid=True, gridColor="#EBEEE3")),
        tooltip=[alt.Tooltip("Date:T"), alt.Tooltip(f"{value_col}:Q", format=".1f")],
    )

    area = alt.Chart(df).mark_area(opacity=0.12, color=color_dark).encode(
        x="Date:T", y=f"{value_col}:Q"
    )

    chart = (area + bars).properties(height=280).configure_view(strokeWidth=0)
    st.altair_chart(chart, use_container_width=True)


def load_data():
    conn = sqlite3.connect(DB_PATH)
    try:
        df_bio = pd.read_sql_query("SELECT * FROM biometrics", conn)
        df_cycle = pd.read_sql_query("SELECT * FROM cycle_logs", conn)
    except Exception as e:
        st.error(f"Database Read Error: {e}")
        return pd.DataFrame(), pd.DataFrame()
    finally:
        conn.close()

    if df_bio.empty:
        df_bio = pd.DataFrame(columns=["id", "metric_type", "timestamp", "value"])
    else:
        df_bio["timestamp"] = pd.to_datetime(df_bio["timestamp"])

    if df_cycle.empty:
        df_cycle = pd.DataFrame(columns=["id", "date", "period_start", "abdominal_pain_severity"])
    else:
        df_cycle["date"] = pd.to_datetime(df_cycle["date"])

    return df_bio, df_cycle


@st.cache_data(show_spinner="Generating insight...")
def cached_insight(cache_key: str, metric_label: str, stats: dict, corr_info: dict):
    return generate_insight(metric_label, stats, corr_info)


render_hero()

try:
    with st.container(border=True):
        st.markdown('<span class="bco-eyebrow">Step 1</span>', unsafe_allow_html=True)
        st.subheader("Target Metric Selection")
        st.write("Choose the primary health metric you want to analyze across the engine:")
        target_metric = st.selectbox(
            label="Select Core Health Metric",
            options=list(METRIC_LABEL_TO_DB.keys()),
            index=0,
            label_visibility="collapsed"
        )

    st.write("")

    df_bio, df_cycle = load_data()
    db_metric_name = METRIC_LABEL_TO_DB[target_metric]

    if not df_bio.empty:
        df_bio["Date"] = df_bio["timestamp"].dt.date
        df_wide = df_bio.pivot_table(
            index="Date", columns="metric_type", values="value", aggfunc="mean"
        ).reset_index()
        df_wide["Date"] = pd.to_datetime(df_wide["Date"])
    else:
        df_wide = pd.DataFrame(columns=["Date"])

    has_data = db_metric_name in df_wide.columns and not df_wide[db_metric_name].dropna().empty

    with st.container(border=True):
        st.markdown('<span class="bco-eyebrow">Baseline</span>', unsafe_allow_html=True)
        st.subheader("Phase Variance Engine")
        st.write("Identifies deviations and shifts from your baseline normal intervals.")

        if has_data:
            series = df_wide[db_metric_name].dropna()
            current_val = series.iloc[-1]
            avg_val = series.mean()
            variance = current_val - avg_val

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label=f"Latest {target_metric}", value=round(current_val, 1), delta=f"{variance:.1f} vs Avg")
            with col2:
                st.metric(label="7-Day Rolling Baseline", value=round(series.tail(7).mean(), 1))
            with col3:
                st.metric(label="30-Day Historical Average", value=round(avg_val, 1))
        else:
            st.info(f"No data yet for **{target_metric}**. Sync some data via /api/v1/specialized-sync.")

    st.write("")

    with st.container(border=True):
        st.markdown('<span class="bco-eyebrow">Trend</span>', unsafe_allow_html=True)
        st.subheader("Trajectory & Correlation Timeline")
        st.write(f"Visualizing the historical timeline for **{target_metric}**.")

        if has_data:
            chart_df = df_wide[["Date", db_metric_name]].dropna()
            gradient_bar_chart(chart_df, db_metric_name, target_metric, MOSS, SAGE)

            if not df_cycle.empty:
                show_cycle = st.toggle("Overlay Abdominal Pain Severity (cycle log)", value=False)
                if show_cycle:
                    cycle_df = df_cycle.rename(columns={"date": "Date"})[["Date", "abdominal_pain_severity"]]
                    gradient_bar_chart(cycle_df, "abdominal_pain_severity", "Pain Severity", BRICK, GOLD)
        else:
            st.info("No data to chart yet.")

    st.write("")

    with st.container(border=True):
        st.markdown('<span class="bco-eyebrow">Analysis</span>', unsafe_allow_html=True)
        st.subheader("Automated Insights Layer")
        st.write("Analysis based on your current data and selected metric:")

        if has_data:
            metric_series = df_wide[db_metric_name].dropna()
            stats = compute_metric_stats(metric_series)
            corr_info = compute_cycle_correlation(df_wide, df_cycle, db_metric_name)

            cache_key = hashlib.md5(f"{db_metric_name}{stats}{corr_info}".encode()).hexdigest()
            insight_text, source = cached_insight(cache_key, target_metric, stats, corr_info)

            st.info(insight_text)
            if source == "ai":
                st.caption("✨ AI-generated insight")
            else:
                st.caption("📊 Rule-based insight — add Anthropic API credit to enable AI-generated insights")
        else:
            st.info("Select a metric with synced data to generate an insight here.")

except Exception as e:
    st.error(f"Internal Dashboard Error: {e}")
    st.info("Waiting for data. Run load_data.py to populate the database.")