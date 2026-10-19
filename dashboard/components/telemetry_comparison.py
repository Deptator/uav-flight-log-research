"""Synchronized comparison of UAV telemetry signals with a shared time window."""

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.log_parser import parse_flight_log

from src.telemetry_window_export import build_telemetry_window_excel


def prepare_comparison_data(log_path):
    """Extract CTUN, GPS and RCOU using one common recording-time origin."""
    telemetry = parse_flight_log(
        log_path,
        message_types=["CTUN", "GPS", "RCOU"],
    )

    prepared = {}
    first_times = []

    for message_type in ("CTUN", "GPS", "RCOU"):
        frame = telemetry.get(message_type)
        if frame is None or frame.empty or "TimeUS" not in frame:
            continue

        frame = frame.copy()
        frame["TimeSec"] = pd.to_numeric(frame["TimeUS"], errors="coerce") / 1_000_000
        frame = frame.dropna(subset=["TimeSec"]).sort_values("TimeSec")
        frame = frame[frame["TimeSec"].map(math.isfinite)]
        if frame.empty:
            continue

        prepared[message_type] = frame
        first_times.append(float(frame["TimeSec"].iloc[0]))

    if not first_times:
        return {}

    origin = min(first_times)
    for frame in prepared.values():
        frame["ElapsedSec"] = frame["TimeSec"] - origin

    return prepared


def render_telemetry_comparison(log_path):
    """Show three telemetry channels on aligned axes in a chosen time range."""
    st.subheader("🔬 Multi-Signal Telemetry Comparison")
    telemetry = prepare_comparison_data(log_path)

    if not telemetry:
        st.warning("No comparable telemetry was found.")
        return

    latest_time = max(float(frame["ElapsedSec"].max()) for frame in telemetry.values())
    if not math.isfinite(latest_time) or latest_time <= 0:
        st.warning("Not enough valid telemetry timestamps to select a time window.")
        return

    max_seconds = max(1, math.ceil(latest_time))
    start_sec, end_sec = st.slider(
        "Select recording time window (seconds)",
        min_value=0,
        max_value=max_seconds,
        value=(0, max_seconds),
        step=1,
        key="telemetry_comparison_time_window",
    )

    if start_sec == end_sec:
        st.info("Select a time window with a nonzero duration.")
        return

    st.caption(f"Viewing {start_sec:,}–{end_sec:,} seconds of the recording")

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("CTUN Altitude", "GPS Ground Speed", "RCOU Channel C1"),
    )

    ctun = telemetry.get("CTUN")
    if ctun is not None and "Alt" in ctun.columns:
        current = ctun.loc[ctun["ElapsedSec"].between(start_sec, end_sec)]
        altitude = pd.to_numeric(current["Alt"], errors="coerce")
        fig.add_trace(
            go.Scatter(x=current["ElapsedSec"], y=altitude, name="Altitude", mode="lines"),
            row=1, col=1,
        )

    gps = telemetry.get("GPS")
    if gps is not None and {"Status", "Spd"}.issubset(gps.columns):
        status = pd.to_numeric(gps["Status"], errors="coerce")
        speed = pd.to_numeric(gps["Spd"], errors="coerce")
        valid = gps["ElapsedSec"].between(start_sec, end_sec) & (status >= 3) & (speed >= 0) & speed.notna()
        fig.add_trace(
            go.Scatter(x=gps.loc[valid, "ElapsedSec"], y=speed.loc[valid], name="GPS Speed", mode="lines"),
            row=2, col=1,
        )

    rcou = telemetry.get("RCOU")
    if rcou is not None and "C1" in rcou.columns:
        current = rcou.loc[rcou["ElapsedSec"].between(start_sec, end_sec)]
        pwm = pd.to_numeric(current["C1"], errors="coerce")
        fig.add_trace(
            go.Scatter(x=current["ElapsedSec"], y=pwm, name="RCOU C1", mode="lines"),
            row=3, col=1,
        )

    if not fig.data or all(len(trace.x) == 0 for trace in fig.data):
        st.warning("No telemetry samples were recorded within the selected time window.")
        return

    fig.update_yaxes(title_text="Altitude (m)", row=1, col=1)
    fig.update_yaxes(title_text="Speed (m/s)", row=2, col=1)
    fig.update_yaxes(title_text="PWM (µs)", row=3, col=1)
    fig.update_xaxes(title_text="Elapsed Recording Time (seconds)", row=3, col=1)
    fig.update_xaxes(range=[start_sec, end_sec])
    fig.update_layout(height=850, hovermode="x", legend=dict(orientation="h", y=1.08))
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "All signals use a common timestamp reference. GPS speed samples require "
        "a 3D-or-better fix and non-negative speed. Missing data is not filled. "
        "RCOU values represent controller outputs, not measured RPM or thrust."
    )
    try:
        window_excel = build_telemetry_window_excel(
            telemetry,
            start_sec,
            end_sec,
        )

        st.download_button(
            label="📥 Download Selected Time Window (.xlsx)",
            data=window_excel,
            file_name=f"uav_telemetry_{start_sec}_{end_sec}s.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            key="download_telemetry_window",
        )

    except (ValueError, OSError) as exc:
        st.warning(f"Time-window Excel export unavailable: {exc}")