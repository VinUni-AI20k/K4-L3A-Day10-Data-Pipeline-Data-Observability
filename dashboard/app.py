"""Observability Dashboard — Data Quality & Drift Monitor."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"

st.set_page_config(page_title="Data Observability Dashboard", layout="wide")
st.title("Data Observability Dashboard")
st.caption("GOHOME — K4-L3-DAY10 | Real-time quality, freshness & 3-state comparison")


def _load(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


# ── Load artifacts ──────────────────────────────────────────────────────────
baseline_q   = _load(DATA / "quality/baseline_quality_report.json")
corrupted_q  = _load(DATA / "quality/corrupted_quality_report.json")
repaired_q   = _load(DATA / "quality/repaired_quality_report.json")

baseline_f   = _load(DATA / "quality/freshness_report.json")
corrupted_f  = _load(DATA / "quality/corrupted_freshness_report.json")
repaired_f   = _load(DATA / "quality/repaired_freshness_report.json")

baseline_m   = _load(DATA / "results/baseline_metrics.json")
corrupted_m  = _load(DATA / "results/corrupted_metrics.json")
repaired_m   = _load(DATA / "results/repaired_metrics.json")

clean_json   = DATA / "clean/papers_clean.json"


# ── Section 1: Overall Status ────────────────────────────────────────────────
st.header("1. Overall Pipeline Status")
col1, col2, col3 = st.columns(3)
states = [
    ("Baseline",  baseline_q,  baseline_f,  baseline_m),
    ("Corrupted", corrupted_q, corrupted_f, corrupted_m),
    ("Repaired",  repaired_q,  repaired_f,  repaired_m),
]
for col, (label, q, f, m) in zip([col1, col2, col3], states):
    gx_ok = q.get("success", None)
    fresh = f.get("is_fresh", None)
    hit   = m.get("retrieval_hit_rate")
    with col:
        st.subheader(label)
        st.metric("GX Quality", "✅ PASS" if gx_ok else "❌ FAIL" if gx_ok is False else "—")
        st.metric("Freshness",  "✅ Fresh" if fresh else "❌ Stale" if fresh is False else "—")
        st.metric("Hit Rate",   f"{hit:.4f}" if hit is not None else "—")


# ── Section 2: GX Expectations Detail ───────────────────────────────────────
st.header("2. Great Expectations — Detailed Results")
rows = []
for label, q in [("Baseline", baseline_q), ("Corrupted", corrupted_q), ("Repaired", repaired_q)]:
    for r in q.get("results", []):
        exp  = r["expectation"].replace("expect_", "").replace("_", " ")
        col  = r.get("kwargs", {}).get("column", "")
        rows.append({
            "State":       label,
            "Expectation": exp + (f" ({col})" if col else ""),
            "Result":      "✅ PASS" if r["success"] else "❌ FAIL",
        })
if rows:
    df_gx = pd.DataFrame(rows)
    pivot  = df_gx.pivot(index="Expectation", columns="State", values="Result")
    st.dataframe(pivot, use_container_width=True)


# ── Section 3: Freshness SLA ─────────────────────────────────────────────────
st.header("3. Freshness SLA — Stale Ratio per State")
fresh_rows = [
    {
        "State":       label,
        "Stale Rows":  f.get("stale_rows", 0),
        "Total Rows":  f.get("total_rows", 0),
        "Stale Ratio": f.get("stale_ratio", 0),
        "is_fresh":    "✅" if f.get("is_fresh") else "❌",
    }
    for label, f in [("Baseline", baseline_f), ("Corrupted", corrupted_f), ("Repaired", repaired_f)]
    if f
]
if fresh_rows:
    df_fresh = pd.DataFrame(fresh_rows)
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.dataframe(df_fresh, use_container_width=True, hide_index=True)
    with col_b:
        st.bar_chart(
            df_fresh.set_index("State")["Stale Ratio"],
            color="#FF6B6B",
        )
        st.caption("Dashed line = 25% threshold (is_fresh=False if exceeded)")


# ── Section 4: Age Distribution ──────────────────────────────────────────────
st.header("4. Paper Age Distribution (Baseline)")
if clean_json.exists():
    df = pd.read_json(clean_json)
    if "age_days" in df.columns:
        st.bar_chart(
            df["age_days"].value_counts().sort_index().rename("count"),
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Median age (days)", int(df["age_days"].median()))
        c2.metric("Max age (days)",    int(df["age_days"].max()))
        c3.metric("Stale (>180d)",     int((df["age_days"] > 180).sum()))


# ── Section 5: 3-State Metrics Comparison ───────────────────────────────────
st.header("5. Agent Metrics — 3-State Comparison")
metric_keys = ["retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"]
metric_rows = {
    k: {
        "Baseline":  baseline_m.get(k),
        "Corrupted": corrupted_m.get(k),
        "Repaired":  repaired_m.get(k),
    }
    for k in metric_keys
    if any(m.get(k) is not None for m in [baseline_m, corrupted_m, repaired_m])
}
if metric_rows:
    df_m = pd.DataFrame(metric_rows).T.astype(float)
    col_left, col_right = st.columns([1, 2])
    with col_left:
        st.dataframe(df_m.style.format("{:.4f}"), use_container_width=True)
    with col_right:
        st.bar_chart(df_m[["Baseline", "Corrupted", "Repaired"]])


# ── Section 6: Corruption Log ────────────────────────────────────────────────
st.header("6. Corruption Log")
log_path = DATA / "results/corruption_log.json"
if log_path.exists():
    log = json.loads(log_path.read_text())
    for entry in log:
        with st.expander(f"🔴 {entry['type']} — {entry['count']} records"):
            st.write(entry["description"])
            st.code(", ".join(entry.get("affected_ids", [])))
else:
    st.info("Run `python script/run_corruption_flow.py` to generate corruption log.")
