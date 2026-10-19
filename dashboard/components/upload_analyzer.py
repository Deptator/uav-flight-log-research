"""Streamlit interface for analyzing uploaded ArduPilot BIN recordings."""

import streamlit as st

from src.upload_processing import analyze_uploaded_log
from src.excel_export import build_excel_report
from tempfile import TemporaryDirectory
from pathlib import Path


def render_upload_analyzer():
    st.subheader("📤 Upload & Analyze")

    st.caption(
        "Analyze a new ArduPilot BIN recording. "
        "Existing dataset reports remain unchanged."
    )

    uploaded_file = st.file_uploader(
        "Choose a UAV flight log",
        type=["bin"],
        key="uav_log_uploader",
    )

    if uploaded_file is None:
        st.info("Select a .bin recording to begin.")
        return

    st.write("Selected recording:", uploaded_file.name)

    if st.button("Analyze Recording", type="primary"):
        try:
            with st.spinner("Processing UAV telemetry..."):
                result = analyze_uploaded_log(
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                )

            st.session_state["uploaded_analysis"] = result
            st.session_state["uploaded_filename"] = uploaded_file.name

        except (ValueError, OSError) as exc:
            st.session_state.pop("uploaded_analysis", None)
            st.session_state.pop("uploaded_filename", None)
            st.error(f"Recording could not be analyzed: {exc}")
            return

    result = st.session_state.get("uploaded_analysis")

    if (
        result is None
        or st.session_state.get("uploaded_filename") != uploaded_file.name
    ):
        return

    analysis = result["Analysis"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Armed Sessions", len(analysis["ArmedSessions"]))
    col2.metric("Activity Segments", len(analysis["ActivitySegments"]))
    col3.metric("Session Report Rows", len(analysis["SessionReport"]))

    st.markdown("#### Session Report")
    st.dataframe(
        analysis["SessionReport"],
        hide_index=True,
        use_container_width=True,
    )

    csv_data = analysis["SessionReport"].to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 Download Session Report (CSV)",
        data=csv_data,
        file_name=f"{result['Filename']}_session_report.csv",
        mime="text/csv",
        key="download_uploaded_session_report",
    )


    with TemporaryDirectory(prefix="uav_excel_export_") as temp_dir:
        raw_log_path = Path(temp_dir) / "recording.bin"
        raw_log_path.write_bytes(uploaded_file.getvalue())

        excel_data = build_excel_report(
            analysis,
            recording_name=result["Filename"],
            raw_log_path=raw_log_path,
        )
    st.download_button(
        label="📊 Download Full Excel Report (.xlsx)",
        data=excel_data,
        file_name=f"{result['Filename']}_analysis.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        key="download_uploaded_excel_report",
    )

    st.caption(
        "Session classifications are experimental research estimates, "
        "not independently confirmed flight events."
    )
