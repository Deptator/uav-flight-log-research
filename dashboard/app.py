"""UAV Flight Analysis System — local Streamlit dashboard."""

from pathlib import Path

import pandas as pd
import streamlit as st

from components.recording_inventory import render_recording_inventory
from components.session_statistics import render_session_statistics
from components.session_explorer import render_session_explorer
from components.anomaly_explorer import render_anomaly_explorer

PROJECT_ROOT = Path(__file__).resolve().parent.parent


SESSIONS_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "analysis"
    / "consolidated_flight_sessions.csv"
)

if SESSIONS_PATH.is_file():
    sessions = pd.read_csv(SESSIONS_PATH)
    st.divider()
    render_session_statistics(sessions)
else:
    st.warning("Consolidated session dataset not found.")


    
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MASTER_INDEX_PATH = (
    PROJECT_ROOT / "outputs" / "diagnostics" / "uav_dataset_master_index.csv"
)

st.set_page_config(
    page_title="UAV Flight Analysis",
    page_icon="🚁",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data
def load_master_index(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


st.title("🚁 UAV Flight Analysis System")
st.caption(
    "Local research dashboard | Flight-log processing, statistics and anomaly analysis"
)
st.divider()

if not MASTER_INDEX_PATH.is_file():
    st.error("Master dataset index not found.")
    st.code(str(MASTER_INDEX_PATH))
    st.stop()

master_index = load_master_index(str(MASTER_INDEX_PATH))

st.subheader("Dataset Overview")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Recordings", len(master_index))
col2.metric("Analyzed Recordings", int(master_index["Status"].eq("SUCCESS").sum()))
col3.metric(
    "No Complete Sessions", int(master_index["Status"].eq("NO_COMPLETE_SESSIONS").sum())
)
col4.metric(
    "Missing ARM", int(master_index["DiagnosticStatus"].eq("MISSING_ARM").sum())
)

st.divider()
render_recording_inventory(master_index)

st.caption(
    "Analysis results are research estimates. Detected motor activity does not "
    "independently confirm airborne flight."
)

if SESSIONS_PATH.is_file():
    st.divider()
    render_session_explorer(sessions) 

ANOMALIES_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "analysis"
    / "anomalies"
    / "session_anomalies.csv"
)

if ANOMALIES_PATH.is_file():
    anomalies = pd.read_csv(ANOMALIES_PATH)
    st.divider()
    render_anomaly_explorer(anomalies)
else:
    st.warning("Anomaly report not found.")