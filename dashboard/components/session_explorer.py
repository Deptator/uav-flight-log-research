import pandas as pd
import streamlit as st


def render_session_explorer(sessions: pd.DataFrame):
    st.subheader("🔎 Recording Session Explorer")

    recordings = sorted(sessions["LogFile"].unique())

    selected_log = st.selectbox(
        "Select a UAV recording",
        recordings,
        key="session_explorer_recording"
    )

    selected_sessions = sessions.loc[
        sessions["LogFile"] == selected_log
    ].copy()

    total_sessions = len(selected_sessions)
    activity_segments = int(
        selected_sessions["ActivitySegments"].sum()
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Armed Sessions", total_sessions)
    col2.metric("Activity Segments", activity_segments)
    col3.metric(
        "Total Armed Duration",
        f"{selected_sessions['ArmedDurationSec'].sum():.1f} s"
    )

    st.markdown("#### Session Details")

    st.dataframe(
        selected_sessions[
            [
                "Session",
                "ArmedDurationSec",
                "ActivityRatio",
                "CoverageRatio",
                "SessionClassification"
            ]
        ],
        hide_index=True,
        use_container_width=True
    )

    st.markdown("#### Motor Activity by Session")

    chart_data = selected_sessions[
        ["Session", "ActivityRatio"]
    ].copy()

    chart_data["ActivityRatio"] *= 100

    st.bar_chart(
        chart_data,
        x="Session",
        y="ActivityRatio",
        x_label="Armed Session",
        y_label="Detected Motor Activity (%)"
    )