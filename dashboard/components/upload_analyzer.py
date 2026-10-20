"""Streamlit interface for analyzing uploaded ArduPilot BIN recordings."""

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st

from components.telemetry_comparison import render_telemetry_comparison
from components.telemetry_visualizer import (
    render_altitude_chart,
    render_gps_speed_chart,
    render_motor_pwm_chart,
)
from src.excel_export import build_excel_report
from src.full_telemetry_export import build_full_telemetry_excel
from src.upload_processing import analyze_uploaded_log


XLSX_MIME = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet"
)


def _clear_uploaded_results():
    """Remove results tied to the previously uploaded file."""
    for key in (
        "uploaded_analysis",
        "uploaded_file_signature",
        "complete_telemetry_excel",
        "complete_telemetry_signature",
    ):
        st.session_state.pop(key, None)


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
        _clear_uploaded_results()
        st.info("Select a .bin recording to begin.")
        return

    content = uploaded_file.getvalue()
    file_signature = (uploaded_file.name, sha256(content).hexdigest())
    st.write("Selected recording:", uploaded_file.name)

    if st.session_state.get("uploaded_file_signature") != file_signature:
        _clear_uploaded_results()

    if st.button("Analyze Recording", type="primary"):
        _clear_uploaded_results()
        try:
            with st.spinner("Processing UAV telemetry..."):
                result = analyze_uploaded_log(uploaded_file.name, content)
            st.session_state["uploaded_analysis"] = result
            st.session_state["uploaded_file_signature"] = file_signature
        except (ValueError, OSError) as exc:
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

    # This path exists only during the current Streamlit rerun.
    # All consumers must finish reading it before exiting this block.
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

        st.divider()
        try:
            render_telemetry_comparison(raw_log_path)
        except (ValueError, OSError, KeyError) as exc:
            st.warning(f"Multi-signal comparison unavailable: {exc}")

        try:
            excel_data = build_excel_report(
                analysis,
                recording_name=result["Filename"],
                raw_log_path=raw_log_path,
            )
        except (ValueError, OSError, KeyError) as exc:
            excel_data = None
            st.warning(f"Excel report unavailable: {exc}")

        # The full 55-message workbook is generated ONLY by this button.
        # Its bytes are retained across Streamlit reruns for this exact file.
        if st.button("Generate Complete Raw Telemetry (.xlsx)",
                     key="generate_complete_raw_telemetry"):
            try:
                with st.spinner("Exporting all available telemetry messages..."):
                    complete_data = build_full_telemetry_excel(raw_log_path)
                st.session_state["complete_telemetry_excel"] = complete_data
                st.session_state["complete_telemetry_signature"] = file_signature
                st.success("Complete raw telemetry workbook is ready to download.")
            except (ValueError, OSError, TypeError) as exc:
                st.session_state.pop("complete_telemetry_excel", None)
                st.session_state.pop("complete_telemetry_signature", None)
                st.error(f"Complete telemetry export failed: {exc}")

    st.divider()
    st.markdown("### Download Reports")

    csv_data = analysis["SessionReport"].to_csv(index=False).encode("utf-8-sig")
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
            mime=XLSX_MIME,
            key="download_uploaded_excel_report",
        )

    if (
        st.session_state.get("complete_telemetry_signature") == file_signature
        and st.session_state.get("complete_telemetry_excel") is not None
    ):
        st.download_button(
            label="📚 Download Complete Raw Telemetry (.xlsx)",
            data=st.session_state["complete_telemetry_excel"],
            file_name=f"{Path(result['Filename']).stem}_complete_telemetry.xlsx",
            mime=XLSX_MIME,
            key="download_complete_raw_telemetry",
        )

    st.caption(
        "Session classifications are experimental research estimates, "
        "not independently confirmed flight events."
    )
