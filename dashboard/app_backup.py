"""UAV Flight Analysis System — local Streamlit dashboard."""

from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from components.anomaly_explorer import render_anomaly_explorer
from components.recording_inventory import render_recording_inventory
from components.session_explorer import render_session_explorer
from components.session_statistics import render_session_statistics
from components.telemetry_diagnostics import render_telemetry_diagnostics


st.set_page_config(
    page_title="UAV Flight Analysis",
    page_icon="🚁",
    layout="wide",
    initial_sidebar_state="expanded",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MASTER_INDEX_PATH = PROJECT_ROOT / "outputs" / "diagnostics" / "uav_dataset_master_index.csv"
SESSIONS_PATH = PROJECT_ROOT / "outputs" / "analysis" / "consolidated_flight_sessions.csv"
ANOMALIES_PATH = PROJECT_ROOT / "outputs" / "analysis" / "anomalies" / "session_anomalies.csv"
DIAGNOSTICS_PATH = PROJECT_ROOT / "outputs" / "diagnostics" / "missing_arm_telemetry_inventory.csv"


@st.cache_data
def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def require_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.is_file():
        st.error(f"{label} not found.")
        st.code(str(path))
        st.stop()
    return load_csv(str(path))


st.sidebar.title("🚁 UAV Research")
page = st.sidebar.radio(
    "Navigation",
    [
        "Overview",
        "Recording Inventory",
        "Session Statistics",
        "Session Explorer",
        "Anomaly Explorer",
        "Telemetry Diagnostics",
    ],
    key="dashboard_navigation",
)

st.title("🚁 UAV Flight Analysis System")
st.caption("Local research dashboard | Flight-log processing, statistics and anomaly analysis")
st.divider()

if page == "Overview":
    master_index = require_csv(MASTER_INDEX_PATH, "Master dataset index")
    st.subheader("Dataset Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Recordings", len(master_index))
    col2.metric("Analyzed Recordings", int(master_index["Status"].eq("SUCCESS").sum()))
    col3.metric(
        "No Complete Sessions",
        int(master_index["Status"].eq("NO_COMPLETE_SESSIONS").sum()),
    )
    col4.metric("Missing ARM", int(master_index["DiagnosticStatus"].eq("MISSING_ARM").sum()))


    st.markdown("#### Recording Processing Outcomes")

    status_counts = (
        master_index["Status"]
        .value_counts()
        .rename_axis("Processing Status")
        .reset_index(name="Recordings")
    )

    st.bar_chart(
        status_counts,
        x="Processing Status",
        y="Recordings",
        horizontal=True,
    )

    st.markdown("#### Top 10 Recordings by Motor Activity")

    RECORDING_STATS_PATH = (
        PROJECT_ROOT
        / "outputs"
        / "analysis"
        / "statistics"
        / "recordings.csv"
    )

    if RECORDING_STATS_PATH.is_file():
        recording_stats = pd.read_csv(RECORDING_STATS_PATH)

        top_recordings = recording_stats.nlargest(
            10, "TotalActivitySec"
        )

        st.bar_chart(
            top_recordings,
            x="LogFile",
            y="TotalActivitySec",
            x_label="Recording",
            y_label="Detected Motor Activity (seconds)",
        )
    else:
        st.warning("Recording statistics report not found.")

elif page == "Recording Inventory":
    master_index = require_csv(MASTER_INDEX_PATH, "Master dataset index")
    render_recording_inventory(master_index)

elif page == "Session Statistics":
    sessions = require_csv(SESSIONS_PATH, "Consolidated session dataset")
    render_session_statistics(sessions)

elif page == "Session Explorer":
    sessions = require_csv(SESSIONS_PATH, "Consolidated session dataset")
    render_session_explorer(sessions)

elif page == "Anomaly Explorer":
    anomalies = require_csv(ANOMALIES_PATH, "Anomaly report")
    render_anomaly_explorer(anomalies)

elif page == "Telemetry Diagnostics":
    diagnostics = require_csv(DIAGNOSTICS_PATH, "Missing-ARM telemetry inventory")
    render_telemetry_diagnostics(diagnostics)

st.divider()
st.caption(
    "Analysis results are research estimates. Detected motor activity and anomaly flags "
    "do not independently confirm airborne flight or UAV faults."
)
