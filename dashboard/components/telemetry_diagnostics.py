import pandas as pd
import streamlit as st


def render_telemetry_diagnostics(diagnostics: pd.DataFrame):
    st.subheader("📡 Telemetry Diagnostics")

    st.caption(
        "Recording-level telemetry inspection for logs "
        "without ARM messages. No armed sessions or flight "
        "classifications are inferred."
    )

    total_logs = len(diagnostics)
    gps_available = int(diagnostics["GPSRecords"].gt(0).sum())
    gps_missing = int(diagnostics["GPSRecords"].eq(0).sum())

    col1, col2, col3 = st.columns(3)

    col1.metric("Missing-ARM Recordings", total_logs)
    col2.metric("With GPS Telemetry", gps_available)
    col3.metric("Without GPS Telemetry", gps_missing)

    gps_filter = st.selectbox(
        "GPS availability",
        ["All recordings", "GPS available", "GPS missing"],
        key="telemetry_gps_filter",
    )

    filtered = diagnostics.copy()

    if gps_filter == "GPS available":
        filtered = filtered[filtered["GPSRecords"] > 0]
    elif gps_filter == "GPS missing":
        filtered = filtered[filtered["GPSRecords"] == 0]

    st.caption(f"Showing {len(filtered)} of {total_logs} recordings")

    st.dataframe(
        filtered[
            [
                "LogFile",
                "DiagnosticStatus",
                "RCOURecords",
                "CTUNRecords",
                "GPSRecords",
                "BARORecords",
                "RCOUSpanSec",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )

    st.markdown("#### Individual Recording Diagnostics")

    selected_log = st.selectbox(
        "Select recording",
        sorted(filtered["LogFile"].tolist()),
        key="telemetry_recording",
    ) if not filtered.empty else None

    if selected_log is not None:
        record = filtered.loc[
            filtered["LogFile"] == selected_log
        ].iloc[0]

        col1, col2, col3 = st.columns(3)

        col1.metric("RCOU Records", int(record["RCOURecords"]))
        col2.metric("GPS Records", int(record["GPSRecords"]))
        col3.metric("RCOU Timestamp Span", f"{record['RCOUSpanSec']:.1f} s")

    st.info(
        "Timestamp span does not imply continuous telemetry coverage. "
        "Missing ARM events prevent armed-session reconstruction."
    )