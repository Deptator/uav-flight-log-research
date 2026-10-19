"""Streamlit interface for analyzing uploaded ArduPilot BIN recordings."""

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st


from src.upload_processing import analyze_uploaded_log
from src.excel_export import build_excel_report
from components.telemetry_visualizer import (
    render_altitude_chart,
    render_gps_speed_chart,
    render_motor_pwm_chart,
)


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
        st.session_state.pop("uploaded_analysis", None)
        st.session_state.pop("uploaded_file_signature", None)
        st.info("Select a .bin recording to begin.")
        return

    content = uploaded_file.getvalue()
    file_signature = (
        uploaded_file.name,
        sha256(content).hexdigest(),
    )

    st.write("Selected recording:", uploaded_file.name)

    # Clear old results whenever the uploaded recording changes.
    if st.session_state.get("uploaded_file_signature") != file_signature:
        st.session_state.pop("uploaded_analysis", None)
        st.session_state.pop("uploaded_file_signature", None)

    if st.button("Analyze Recording", type="primary"):
        try:
            with st.spinner("Processing UAV telemetry..."):
                result = analyze_uploaded_log(
                    uploaded_file.name,
                    content,
                )

            st.session_state["uploaded_analysis"] = result
            st.session_state["uploaded_file_signature"] = file_signature

        except (ValueError, OSError) as exc:
            st.session_state.pop("uploaded_analysis", None)
            st.session_state.pop("uploaded_file_signature", None)
            st.error(f"Recording could not be analyzed: {exc}")
            return

    result = st.session_state.get("uploaded_analysis")

    if result is None:
        st.info("Click 'Analyze Recording' to view results.")
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

    # Reuse the uploaded recording for visualization and Excel export.
    with TemporaryDirectory(prefix="uav_telemetry_") as temp_dir:
        raw_log_path = Path(temp_dir) / "recording.bin"
        raw_log_path.write_bytes(content)

        st.divider()
        st.markdown("### Interactive Flight Telemetry")

        try:
            render_altitude_chart(raw_log_path)
        except (ValueError, OSError, KeyError) as exc:
            st.warning(f"Altitude graph unavailable: {exc}")

        try:
            render_gps_speed_chart(raw_log_path)
        except (ValueError, OSError, KeyError) as exc:
            st.warning(f"GPS speed graph unavailable: {exc}")

        try:
            render_motor_pwm_chart(raw_log_path)
        except (ValueError, OSError, KeyError) as exc:
            st.warning(f"Motor PWM graph unavailable: {exc}")

        try:
            excel_data = build_excel_report(
                analysis,
                recording_name=result["Filename"],
                raw_log_path=raw_log_path,
            )
        except (ValueError, OSError, KeyError) as exc:
            excel_data = None
            st.warning(f"Excel report unavailable: {exc}")

    st.divider()
    st.markdown("### Download Reports")

    csv_data = (
        analysis["SessionReport"]
        .to_csv(index=False)
        .encode("utf-8-sig")
    )

    st.download_button(
        label="📥 Download Session Report (CSV)",
        data=csv_data,
        file_name=f"{result['Filename']}_session_report.csv",
        mime="text/csv",
        key="download_uploaded_session_report",
    )

    if excel_data is not None:
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