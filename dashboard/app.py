from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.config import load_settings  # noqa: E402
from observability.quality import run_data_quality_checks  # noqa: E402


st.set_page_config(
    page_title="RAG Data Observability",
    page_icon="📡",
    layout="wide",
)

settings = load_settings(PROJECT_ROOT)


@st.cache_data(show_spinner=False)
def load_dataframe(path_text: str) -> pd.DataFrame:
    path = Path(path_text)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    return pd.read_json(path)


@st.cache_data(show_spinner=False)
def load_json(path_text: str) -> dict:
    return json.loads(Path(path_text).read_text(encoding="utf-8"))


def report_path_for(label: str) -> Path:
    if label == "Baseline":
        return settings.paths.baseline_quality_report
    if label == "Corrupted":
        return settings.paths.corrupted_quality_report
    return settings.paths.quality_dir / "repaired_quality_report.json"


datasets = {
    "Baseline": settings.paths.clean_json,
    "Corrupted": settings.paths.corrupted_clean_json,
    "Repaired": settings.paths.repaired_clean_json,
}
available_datasets = {label: path for label, path in datasets.items() if path.exists()}

st.title("📡 RAG Data Observability")
st.caption("Great Expectations 1.x quality gate · Freshness SLA · Dataset health monitoring")

if not available_datasets:
    st.error("Không tìm thấy dữ liệu clean. Hãy chạy pipeline tạo data/clean trước.")
    st.stop()

with st.sidebar:
    st.header("Điều khiển")
    selected_label = st.selectbox("Trạng thái dữ liệu", list(available_datasets))
    selected_path = available_datasets[selected_label]
    st.code(str(selected_path.relative_to(PROJECT_ROOT)), language=None)
    run_check = st.button("Chạy lại Quality Gate", type="primary", use_container_width=True)

try:
    dataframe = load_dataframe(str(selected_path))
except Exception as exc:
    st.error(f"Không thể đọc dữ liệu: {exc}")
    st.stop()

report_path = report_path_for(selected_label)
if run_check:
    with st.spinner("Đang chạy Great Expectations và Freshness SLA..."):
        report = run_data_quality_checks(dataframe, settings, selected_label.lower())
    load_json.clear()
    st.success(f"Đã cập nhật {report_path.name}")
elif report_path.exists():
    report = load_json(str(report_path))
else:
    report = None

if report:
    status_col, rows_col, passed_col, stale_col = st.columns(4)
    status_col.metric("Quality Gate", "PASS" if report["success"] else "FAIL")
    rows_col.metric("Tổng bản ghi", report.get("total_rows", len(dataframe)))
    statistics = report.get("statistics", {})
    passed_col.metric(
        "Expectations đạt",
        f"{statistics.get('successful_expectations', 0)}/{statistics.get('evaluated_expectations', 0)}",
    )
    freshness = report.get("freshness", {})
    stale_col.metric("Tỷ lệ stale", f"{freshness.get('stale_percent', 0):.2f}%")

    if report["success"]:
        st.success("Dữ liệu đạt Quality Gate và Freshness SLA.")
    else:
        st.error("Dữ liệu không đạt. Kiểm tra expectation thất bại và cảnh báo freshness bên dưới.")

    st.subheader("Chi tiết Quality Gate")
    check_table = pd.DataFrame(report.get("checks", []))
    if not check_table.empty:
        check_table["status"] = check_table["success"].map({True: "✅ PASS", False: "❌ FAIL"})
        columns = [
            column
            for column in ("status", "name", "observed_value", "unexpected_count", "unexpected_percent", "exception")
            if column in check_table.columns
        ]
        st.dataframe(check_table[columns], use_container_width=True, hide_index=True)

    st.subheader("Freshness SLA")
    freshness_cols = st.columns(4)
    freshness_cols[0].metric("Mới nhất", freshness.get("latest_published") or "N/A")
    freshness_cols[1].metric("Cũ nhất", freshness.get("oldest_published") or "N/A")
    freshness_cols[2].metric("Số bài stale", freshness.get("stale_rows", 0))
    freshness_cols[3].metric("Ngưỡng SLA", f"≤ {freshness.get('stale_ratio_limit', 0.25) * 100:.0f}%")
else:
    st.info("Chưa có quality report. Nhấn “Chạy lại Quality Gate” để tạo báo cáo.")

st.subheader("Phân bố tuổi dữ liệu")
if "age_days" in dataframe.columns:
    ages = pd.to_numeric(dataframe["age_days"], errors="coerce").dropna()
    if ages.empty:
        st.warning("Cột age_days không có giá trị hợp lệ.")
    else:
        bins = min(10, max(1, ages.nunique()))
        age_distribution = (
            pd.cut(ages, bins=bins, duplicates="drop")
            .value_counts(sort=False)
            .rename_axis("Khoảng tuổi")
            .reset_index(name="Số bài")
        )
        age_distribution["Khoảng tuổi"] = age_distribution["Khoảng tuổi"].astype(str)
        st.bar_chart(age_distribution, x="Khoảng tuổi", y="Số bài")
else:
    st.warning("Dữ liệu chưa có cột age_days.")

with st.expander("Xem dữ liệu mẫu"):
    st.dataframe(dataframe.head(20), use_container_width=True, hide_index=True)
