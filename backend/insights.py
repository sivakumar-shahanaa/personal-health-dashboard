"""
insights.py

Generates short insights about the user's health data, in two possible modes:

  1. AI mode (preferred): if ANTHROPIC_API_KEY is set AND has credit, sends
     summary stats (never raw data) to Claude, which writes a short insight.

  2. Rule-based fallback (free, no API needed): if the API key is missing,
     unfunded, or unreachable for any reason, we compute the insight locally
     using simple threshold rules on the same stats. No network call, no cost.

The app always shows something useful -- it just quietly downgrades from
"AI-written" to "rule-based" when the API isn't available, and upgrades back
automatically the moment a working API key is in place. No code changes
needed to switch between the two.
"""

import os
import pandas as pd
from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"

_client = None


def get_client():
    """Lazily create the Anthropic client. Returns None if no API key is set."""
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    _client = Anthropic(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# STATS COMPUTATION (shared by both AI and rule-based modes)
# ---------------------------------------------------------------------------

def compute_metric_stats(metric_series: pd.Series) -> dict:
    """Compute summary stats for one metric. Returns a dict, not raw data."""
    if metric_series.empty:
        return {"available": False}

    latest = float(metric_series.iloc[-1])
    avg_30 = float(metric_series.mean())
    avg_7 = float(metric_series.tail(7).mean())

    if avg_7 > avg_30 * 1.02:
        trend = "rising"
    elif avg_7 < avg_30 * 0.98:
        trend = "falling"
    else:
        trend = "stable"

    pct_change = ((avg_7 - avg_30) / avg_30 * 100) if avg_30 != 0 else 0.0

    return {
        "available": True,
        "latest": latest,
        "avg_7": avg_7,
        "avg_30": avg_30,
        "min": float(metric_series.min()),
        "max": float(metric_series.max()),
        "trend": trend,
        "pct_change": pct_change,
        "n": len(metric_series),
    }


def compute_cycle_correlation(df_wide: pd.DataFrame, df_cycle: pd.DataFrame, metric_col: str) -> dict:
    """Correlate the selected metric with logged abdominal pain severity."""
    if df_cycle is None or df_cycle.empty or df_wide.empty or metric_col not in df_wide.columns:
        return {"available": False, "n": 0}

    cycle = df_cycle.copy()
    cycle["Date"] = pd.to_datetime(cycle["date"]).dt.normalize()

    metrics = df_wide[["Date", metric_col]].copy()
    metrics["Date"] = pd.to_datetime(metrics["Date"]).dt.normalize()

    merged = pd.merge(
        metrics, cycle[["Date", "abdominal_pain_severity"]],
        on="Date", how="inner"
    ).dropna()

    if len(merged) < 4:
        return {"available": False, "n": len(merged)}

    corr = merged[metric_col].corr(merged["abdominal_pain_severity"])
    if pd.isna(corr):
        return {"available": False, "n": len(merged)}

    return {"available": True, "corr": float(corr), "n": len(merged)}


def stats_to_text(metric_label: str, stats: dict) -> str:
    """Render stats dict as text, for the AI prompt."""
    if not stats.get("available"):
        return f"No data available yet for {metric_label}."
    return (
        f"{metric_label} -- latest: {stats['latest']:.1f}, 7-day avg: {stats['avg_7']:.1f}, "
        f"30-day avg: {stats['avg_30']:.1f}, min: {stats['min']:.1f}, max: {stats['max']:.1f}, "
        f"recent trend: {stats['trend']} ({stats['pct_change']:+.1f}%), "
        f"readings available: {stats['n']}"
    )


def correlation_to_text(corr_info: dict) -> str:
    """Render correlation dict as text, for the AI prompt."""
    if not corr_info.get("available"):
        n = corr_info.get("n", 0)
        return f"Only {n} overlapping day(s) between this metric and cycle logs -- not enough to assess a relationship yet."
    corr = corr_info["corr"]
    strength = "weak" if abs(corr) < 0.3 else "moderate" if abs(corr) < 0.6 else "strong"
    direction = "positive" if corr > 0 else "negative"
    return f"Correlation with logged abdominal pain severity across {corr_info['n']} overlapping days: {corr:.2f} ({strength} {direction})"


# ---------------------------------------------------------------------------
# RULE-BASED FALLBACK (free, no API call)
# ---------------------------------------------------------------------------

def generate_rule_based_insight(metric_label: str, stats: dict, corr_info: dict) -> str:
    """
    Builds a short insight from simple threshold rules on the computed stats.
    No network call -- works even with zero API credit.
    """
    if not stats.get("available"):
        return f"Not enough data yet to generate an insight for {metric_label}."

    trend = stats["trend"]
    pct = stats["pct_change"]

    if trend == "rising":
        trend_sentence = f"Your {metric_label} has been trending upward recently, up about {abs(pct):.1f}% over its 30-day average."
    elif trend == "falling":
        trend_sentence = f"Your {metric_label} has been trending downward recently, down about {abs(pct):.1f}% from its 30-day average."
    else:
        trend_sentence = f"Your {metric_label} has been fairly stable, close to its 30-day average."

    corr_sentence = ""
    if corr_info.get("available"):
        corr = corr_info["corr"]
        if abs(corr) >= 0.3:
            direction = "tends to rise" if corr > 0 else "tends to fall"
            corr_sentence = (
                f" There may be a link with your cycle log too -- {metric_label} {direction} "
                f"on days with higher logged pain severity, based on {corr_info['n']} overlapping days "
                f"(this is a small sample, so treat it as a loose pattern, not a conclusion)."
            )

    low_n_note = ""
    if stats["n"] < 7:
        low_n_note = " (Based on a small number of readings so far -- this will get more reliable as more data comes in.)"

    return trend_sentence + corr_sentence + low_n_note


# ---------------------------------------------------------------------------
# AI-GENERATED INSIGHT (tries API, auto-falls back on any failure)
# ---------------------------------------------------------------------------

def generate_ai_insight(metric_label: str, stats: dict, corr_info: dict) -> str:
    """Raises an exception on any failure -- caller decides what to do with it."""
    client = get_client()
    if client is None:
        raise RuntimeError("No ANTHROPIC_API_KEY set")

    metric_summary = stats_to_text(metric_label, stats)
    cycle_summary = correlation_to_text(corr_info)

    prompt = f"""You are a cautious personal-health data analyst helping someone
understand their own wearable and cycle-tracking data. You are given SUMMARY
STATISTICS only, not raw data.

Write a short, 2-3 sentence insight about the user's {metric_label} based on
the summary below. If a cycle-log correlation is present and not trivial
("not enough data"), mention it briefly. Use hedging language ("may suggest",
"could indicate") since this is a small personal dataset, not a clinical
diagnosis. Do not give medical advice or diagnose anything. Keep it warm but
factual, no fluff.

Metric summary: {metric_summary}
Cycle log summary: {cycle_summary}
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return text.strip()


def generate_insight(metric_label: str, stats: dict, corr_info: dict) -> tuple[str, str]:
    """
    Tries AI first, falls back to rule-based on ANY failure (no key, no
    credit, network error, etc). Returns (insight_text, source) where source
    is "ai" or "rule_based".
    """
    try:
        text = generate_ai_insight(metric_label, stats, corr_info)
        return text, "ai"
    except Exception:
        text = generate_rule_based_insight(metric_label, stats, corr_info)
        return text, "rule_based"