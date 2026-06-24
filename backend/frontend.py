import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import os
import hashlib
import altair as alt
from datetime import date
from dotenv import load_dotenv

from insights import compute_metric_stats, compute_cycle_correlation, generate_insight

load_dotenv()

st.set_page_config(layout="wide", page_title="Biometric Cycle Optimizer")

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
MOSS   = "#2D5A3D"
SAGE   = "#8FAE8B"
BONE   = "#F6F7F1"
GOLD   = "#D9A441"
BRICK  = "#B5563C"
BLUE   = "#4A6FA5"
INK    = "#1B231D"

PHASE_COLORS = {
    "menstrual":  BRICK,
    "follicular": MOSS,
    "ovulatory":  GOLD,
    "luteal":     BLUE,
    "unknown":    "#CCCCCC",
}

PHASE_LABELS = {
    "menstrual":  "Menstrual",
    "follicular": "Follicular",
    "ovulatory":  "Ovulatory",
    "luteal":     "Luteal",
    "unknown":    "Unknown",
}

# ---------------------------------------------------------------------------
# GLOBAL CSS
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    color: {INK};
}}
.stApp {{ background-color: {BONE}; }}
.block-container {{ padding-top: 1.5rem; max-width: 1100px; }}

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
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 600 200' preserveAspectRatio='none'><path d='M0,140 C80,100 130,180 220,120 C300,70 360,160 460,110 C520,80 560,130 600,100' stroke='%238FAE8B' stroke-width='2' fill='none'/><path d='M0,170 C90,140 150,190 240,150 C320,110 380,180 480,140 C540,115 570,150 600,135' stroke='%238FAE8B' stroke-width='1.4' fill='none'/><path d='M0,60 C70,30 140,70 220,40 C300,10 370,55 460,30 C520,12 560,40 600,25' stroke='%232D5A3D' stroke-width='1.6' fill='none'/></svg>");
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

h2, h3 {{
    font-family: 'Fraunces', serif;
    font-weight: 500;
    color: {FOREST};
}}

div[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: white;
    border: 1px solid #E1E6D9 !important;
    border-radius: 14px !important;
    box-shadow: 0 2px 14px rgba(15, 46, 34, 0.06);
}}

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

/* phase legend pills */
.phase-pill {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    font-weight: 500;
    margin-right: 6px;
    color: white;
}}

/* alert box styling */
.phase-alert {{
    background: {BONE};
    border-left: 4px solid {MOSS};
    border-radius: 8px;
    padding: 1rem 1.2rem;
    font-size: 0.9rem;
    line-height: 1.8;
    white-space: pre-line;
    margin-top: 0.5rem;
}}

div[data-baseweb="select"] > div {{
    border-radius: 8px !important;
    border-color: {SAGE} !important;
}}
div[data-testid="stAlert"] {{ border-radius: 10px; font-size: 0.95rem; }}
[data-testid="stCaptionContainer"] {{
    font-family: 'IBM Plex Mono', monospace;
    color: {MOSS} !important;
}}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------------------------

def load_data():
    conn = sqlite3.connect(DB_PATH)
    try:
        df_bio   = pd.read_sql_query("SELECT * FROM biometrics", conn)
        df_cycle = pd.read_sql_query("SELECT * FROM cycle_logs", conn)
        try:
            df_insights = pd.read_sql_query("SELECT * FROM daily_insights", conn)
        except Exception:
            df_insights = pd.DataFrame()
    except Exception as e:
        st.error(f"Database Read Error: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    finally:
        conn.close()

    if not df_bio.empty:
        df_bio["timestamp"] = pd.to_datetime(df_bio["timestamp"])
    if not df_cycle.empty:
        df_cycle["date"] = pd.to_datetime(df_cycle["date"])
    if not df_insights.empty:
        df_insights["date"] = pd.to_datetime(df_insights["date"])

    return df_bio, df_cycle, df_insights


@st.cache_data(show_spinner="Generating insight...")
def cached_insight(cache_key, metric_label, stats, corr_info):
    return generate_insight(metric_label, stats, corr_info)


# ---------------------------------------------------------------------------
# CHART: DUAL-AXIS PHASE CHART
# ---------------------------------------------------------------------------

def phase_chart(df_wide, df_insights, db_metric_name, metric_label):
    """
    Layered Altair chart:
      - Layer 1: colored background bands per cycle phase
      - Layer 2: gradient bar chart of the selected biometric
      - Layer 3: abdominal pain severity as a line overlay (if cycle data exists)
    """
    chart_df = df_wide[["Date", db_metric_name]].dropna().copy()
    chart_df = chart_df.rename(columns={db_metric_name: "value"})
    chart_df["metric"] = metric_label

    # --- Layer 1: phase background bands ---
    phase_bands = alt.Chart()
    if not df_insights.empty and "cycle_phase" in df_insights.columns:
        bands_df = df_insights[["date", "cycle_phase"]].dropna().copy()
        bands_df = bands_df[bands_df["cycle_phase"] != "unknown"]
        bands_df = bands_df.sort_values("date")
        bands_df["date"] = pd.to_datetime(bands_df["date"])

        # merge chart date range with phase data
        merged = pd.merge(
            chart_df[["Date"]].rename(columns={"Date": "date"}),
            bands_df, on="date", how="left"
        ).fillna("unknown")

        if not merged.empty:
            color_scale = alt.Scale(
                domain=list(PHASE_COLORS.keys()),
                range=list(PHASE_COLORS.values())
            )
            phase_bands = alt.Chart(merged).mark_rect(opacity=0.18).encode(
                x=alt.X("date:T", title=None),
                x2="date:T",
                color=alt.Color("cycle_phase:N", scale=color_scale,
                                legend=alt.Legend(title="Cycle Phase")),
            )

    # --- Layer 2: gradient bars ---
    gradient = alt.Gradient(
        gradient="linear",
        stops=[
            alt.GradientStop(color=SAGE, offset=0),
            alt.GradientStop(color=MOSS, offset=1),
        ],
        x1=1, x2=1, y1=1, y2=0,
    )
    bars = alt.Chart(chart_df).mark_bar(
        color=gradient, cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=12
    ).encode(
        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %d", grid=False)),
        y=alt.Y("value:Q", title=metric_label,
                axis=alt.Axis(grid=True, gridColor="#EBEEE3")),
        tooltip=[
            alt.Tooltip("Date:T", title="Date"),
            alt.Tooltip("value:Q", title=metric_label, format=".1f"),
        ],
    )

    area = alt.Chart(chart_df).mark_area(opacity=0.10, color=MOSS).encode(
        x="Date:T", y="value:Q"
    )

    layers = [area, bars]

    # --- Layer 3: pain severity line overlay ---
    if "df_cycle" in st.session_state and not st.session_state.df_cycle.empty:
        cycle_df = st.session_state.df_cycle.rename(columns={"date": "Date"})[
            ["Date", "abdominal_pain_severity"]
        ].dropna()

        if not cycle_df.empty:
            # scale pain to same y-range as metric for visual clarity
            metric_max = chart_df["value"].max()
            pain_max = cycle_df["abdominal_pain_severity"].max()
            scale_factor = (metric_max / pain_max * 0.4) if pain_max > 0 else 1

            cycle_df = cycle_df.copy()
            cycle_df["pain_scaled"] = cycle_df["abdominal_pain_severity"] * scale_factor

            pain_line = alt.Chart(cycle_df).mark_line(
                color=BRICK, strokeWidth=2, strokeDash=[4, 2]
            ).encode(
                x="Date:T",
                y=alt.Y("pain_scaled:Q", title="Pain (scaled)", axis=None),
                tooltip=[
                    alt.Tooltip("Date:T"),
                    alt.Tooltip("abdominal_pain_severity:Q", title="Pain severity"),
                ],
            )
            pain_points = alt.Chart(cycle_df).mark_point(
                color=BRICK, size=40, filled=True
            ).encode(x="Date:T", y="pain_scaled:Q")

            layers += [pain_line, pain_points]

    chart = alt.layer(*layers).properties(height=300).configure_view(strokeWidth=0)
    st.altair_chart(chart, use_container_width=True)


# ---------------------------------------------------------------------------
# PHASE LEGEND
# ---------------------------------------------------------------------------

def render_phase_legend():
    pills = "".join(
        f'<span class="phase-pill" style="background:{color}">{PHASE_LABELS[phase]}</span>'
        for phase, color in PHASE_COLORS.items()
        if phase != "unknown"
    )
    st.markdown(pills, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# MAIN DASHBOARD
# ---------------------------------------------------------------------------

st.markdown(f"""
<div class="bco-hero">
    <span class="bco-eyebrow">Biometric &middot; Cycle &middot; Recovery</span>
    <div class="bco-hero-title">Personal Health Data Dashboard</div>
    <div class="bco-hero-sub">
        Track cross-metric correlations, detect phase variances, and surface
        behavioral sleep and recovery insights from your own data.
    </div>
</div>
""", unsafe_allow_html=True)

try:
    df_bio, df_cycle, df_insights = load_data()

    # stash df_cycle in session state so phase_chart() can access it
    st.session_state.df_cycle = df_cycle

    # build wide-format biometrics df
    if not df_bio.empty:
        df_bio["Date"] = df_bio["timestamp"].dt.date
        df_wide = df_bio.pivot_table(
            index="Date", columns="metric_type", values="value", aggfunc="mean"
        ).reset_index()
        df_wide["Date"] = pd.to_datetime(df_wide["Date"])
    else:
        df_wide = pd.DataFrame(columns=["Date"])

    # -----------------------------------------------------------------------
    # SECTION 1: METRIC SELECTION
    # -----------------------------------------------------------------------
    with st.container(border=True):
        st.markdown('<span class="bco-eyebrow">Step 1</span>', unsafe_allow_html=True)
        st.subheader("Target Metric Selection")
        st.write("Choose the primary health metric to analyze:")
        target_metric = st.selectbox(
            label="Select Core Health Metric",
            options=list(METRIC_LABEL_TO_DB.keys()),
            index=0,
            label_visibility="collapsed"
        )

    st.write("")
    db_metric_name = METRIC_LABEL_TO_DB[target_metric]
    has_data = db_metric_name in df_wide.columns and not df_wide[db_metric_name].dropna().empty

    # -----------------------------------------------------------------------
    # SECTION 2: PHASE VARIANCE ENGINE (KPI cards)
    # -----------------------------------------------------------------------
    with st.container(border=True):
        st.markdown('<span class="bco-eyebrow">Baseline</span>', unsafe_allow_html=True)
        st.subheader("Phase Variance Engine")
        st.write("Deviations and shifts from your baseline normal intervals.")

        if has_data:
            series = df_wide[db_metric_name].dropna()
            current_val = series.iloc[-1]
            avg_val     = series.mean()
            variance    = current_val - avg_val

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(f"Latest · {target_metric}", round(current_val, 1),
                          delta=f"{variance:.1f} vs Avg")
            with col2:
                st.metric("7-Day Rolling Baseline", round(series.tail(7).mean(), 1))
            with col3:
                st.metric("30-Day Historical Average", round(avg_val, 1))
        else:
            st.info(f"No data yet for **{target_metric}**. Run load_data.py to sync data.")

    st.write("")

    # -----------------------------------------------------------------------
    # SECTION 3: DUAL-AXIS PHASE CHART
    # -----------------------------------------------------------------------
    with st.container(border=True):
        st.markdown('<span class="bco-eyebrow">Trend</span>', unsafe_allow_html=True)
        st.subheader("Trajectory & Cycle Phase Timeline")

        if has_data:
            render_phase_legend()
            st.caption("Background shading = cycle phase. Dashed red line = logged pain severity (if available).")
            st.write("")
            phase_chart(df_wide, df_insights, db_metric_name, target_metric)
        else:
            st.info("No data to chart yet.")

    st.write("")

    # -----------------------------------------------------------------------
    # SECTION 4: PHASE-AWARE ALERTS
    # -----------------------------------------------------------------------
    with st.container(border=True):
        st.markdown('<span class="bco-eyebrow">Phase Alerts</span>', unsafe_allow_html=True)
        st.subheader("Performance & Recovery Alerts")
        st.write("Phase-specific patterns and predictions from your cycle history:")

        if not df_insights.empty and "cycle_phase" in df_insights.columns:
            today = pd.Timestamp(date.today())
            today_row = df_insights[df_insights["date"] == today]

            if today_row.empty:
                # fall back to the most recent date we have
                today_row = df_insights.sort_values("date").iloc[[-1]]

            alert_text = today_row["insight_text"].values[0] if len(today_row) > 0 else None
            current_phase = today_row["cycle_phase"].values[0] if len(today_row) > 0 else "unknown"

            if alert_text:
                phase_color = PHASE_COLORS.get(current_phase, "#CCCCCC")
                st.markdown(
                    f'<div class="phase-alert" style="border-left-color:{phase_color}">'
                    f'{alert_text}'
                    f'</div>',
                    unsafe_allow_html=True
                )
            else:
                st.info("Run phase_engine.py to generate phase-specific alerts.")

            # phase average comparison table
            st.write("")
            st.caption("Per-phase biometric averages across your history:")
            phase_rows = df_insights.groupby("cycle_phase").agg(
                HRV=("hrv_phase_avg", "mean"),
                RHR=("rhr_phase_avg", "mean"),
                Sleep=("sleep_phase_avg", "mean"),
                Steps=("steps_phase_avg", "mean"),
            ).round(1).reset_index()
            phase_rows.columns = ["Phase", "Avg HRV", "Avg RHR", "Avg Sleep %", "Avg Steps"]
            st.dataframe(phase_rows, hide_index=True, use_container_width=True)

        else:
            st.info("Run phase_engine.py after loading data to activate phase alerts.")

    st.write("")

    # -----------------------------------------------------------------------
    # SECTION 5: AI / RULE-BASED INSIGHTS
    # -----------------------------------------------------------------------
    with st.container(border=True):
        st.markdown('<span class="bco-eyebrow">Analysis</span>', unsafe_allow_html=True)
        st.subheader("Automated Insights Layer")
        st.write("Cross-metric analysis based on your current data and selected metric:")

        if has_data:
            metric_series = df_wide[db_metric_name].dropna()
            stats    = compute_metric_stats(metric_series)
            corr_info = compute_cycle_correlation(df_wide, df_cycle, db_metric_name)
            cache_key = hashlib.md5(f"{db_metric_name}{stats}{corr_info}".encode()).hexdigest()
            insight_text, source = cached_insight(cache_key, target_metric, stats, corr_info)

            st.info(insight_text)
            if source == "ai":
                st.caption("✨ AI-generated insight")
            else:
                st.caption("Rule-based insight — add Anthropic API credit to enable AI-generated insights")
        else:
            st.info("Select a metric with synced data to generate an insight here.")

except Exception as e:
    st.error(f"Internal Dashboard Error: {e}")
    st.info("Waiting for data. Run load_data.py then phase_engine.py to populate the database.")