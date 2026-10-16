import pandas as pd
import streamlit as st
import plotly.express as px

def render_anomaly_explorer(anomalies: pd.DataFrame):
    st.subheader("🔍 Anomaly Explorer")

    total = len(anomalies)
    flagged = anomalies["AnomalyFlag"].sum()
    consistent = (
        anomalies["ConsensusStatus"] == "CONSISTENTLY_FLAGGED"
    ).sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Sessions Evaluated", total)
    col2.metric("Isolation Forest Flags", int(flagged))
    col3.metric("Consistently Flagged", int(consistent))

    status = st.selectbox(
        "Show sessions",
        ["Flagged only", "All sessions", "Consistently flagged"],
        key="anomaly_filter"
    )

    if status == "Flagged only":
        filtered = anomalies[anomalies["AnomalyFlag"]].copy()
    elif status == "Consistently flagged":
        filtered = anomalies[
            anomalies["ConsensusStatus"] == "CONSISTENTLY_FLAGGED"
        ].copy()
    else:
        filtered = anomalies.copy()

    filtered = filtered.sort_values(
        "AnomalyScore", ascending=False
    )

    st.caption(f"Showing {len(filtered)} of {total} sessions")

    st.dataframe(
        filtered[
            [
                "LogFile",
                "Session",
                "ArmedDurationSec",
                "ActivityRatio",
                "AnomalyScore",
                "AnomalyFlag",
                "ConsensusStatus"
            ]
        ],
        hide_index=True,
        use_container_width=True
    )

    st.caption(
        "Anomaly flags indicate statistically unusual sessions, "
        "not confirmed UAV faults."
    )

    st.info("DEBUG: Anomaly visualization section reached")

    st.markdown("#### Anomaly Detection Visualization")

    chart_data = anomalies.copy()

    chart_data["ActivityPercent"] = (
        chart_data["ActivityRatio"] * 100
    )

    chart_data["DetectionStatus"] = chart_data[
        "AnomalyFlag"
    ].map({
        True: "Flagged",
        False: "Not Flagged"
    })

    fig = px.scatter(
        chart_data,
        x="ArmedDurationSec",
        y="ActivityPercent",
        color="DetectionStatus",
        hover_data=[
            "LogFile",
            "Session",
            "AnomalyScore",
            "ConsensusStatus"
        ],
        labels={
            "ArmedDurationSec": "Armed Duration (seconds)",
            "ActivityPercent": "Detected Motor Activity (%)"
        },
        color_discrete_map={
            "Flagged": "#FF6B6B",
            "Not Flagged": "#4A90E2"
        },
        title="Isolation Forest — Session Anomalies"
    )

    fig.update_traces(marker=dict(size=9, opacity=0.75))

    st.plotly_chart(
        fig,
        use_container_width=True
    )