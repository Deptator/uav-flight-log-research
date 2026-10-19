"""Interactive UAV telemetry visualizations on a shared recording timeline."""

import pandas as pd
import plotly.express as px
import streamlit as st

from src.log_parser import parse_flight_log


SYNC_MESSAGE_TYPES = ("CTUN", "GPS", "RCOU")


def _load_synchronized_telemetry(log_path):
    """Load the three plotted message types and find their shared time origin.

    TimeUS is a log timestamp in microseconds. The origin is the earliest
    finite timestamp available across CTUN, GPS and RCOU, regardless of
    whether an individual GPS speed sample later passes quality filters.
    """
    telemetry = parse_flight_log(log_path, message_types=list(SYNC_MESSAGE_TYPES))
    starts = []
    for message_type in SYNC_MESSAGE_TYPES:
        frame = telemetry.get(message_type)
        if frame is None or frame.empty or "TimeUS" not in frame.columns:
            continue
        times = pd.to_numeric(frame["TimeUS"], errors="coerce")
        times = times.replace([float("inf"), float("-inf")], float("nan")).dropna()
        if not times.empty:
            starts.append(float(times.min()) / 1_000_000)
    if not starts:
        return telemetry, None
    return telemetry, min(starts)


def _add_elapsed_seconds(frame, origin_sec):
    """Convert TimeUS into seconds since the common recording origin."""
    result = frame.copy()
    result["TimeSec"] = pd.to_numeric(result["TimeUS"], errors="coerce") / 1_000_000
    result["ElapsedSec"] = result["TimeSec"] - origin_sec
    return result


def render_altitude_chart(log_path):
    """Plot recorded CTUN altitude on the shared recording timeline."""
    telemetry, origin_sec = _load_synchronized_telemetry(log_path)
    ctun = telemetry.get("CTUN")

    if ctun is None or ctun.empty:
        st.warning("CTUN altitude telemetry is unavailable.")
        return
    if origin_sec is None or not {"TimeUS", "Alt"}.issubset(ctun.columns):
        st.warning("Required CTUN altitude timestamps or fields are missing.")
        return

    chart_data = _add_elapsed_seconds(ctun[["TimeUS", "Alt"]], origin_sec)
    chart_data["Alt"] = pd.to_numeric(chart_data["Alt"], errors="coerce")
    chart_data = chart_data.replace([float("inf"), float("-inf")], float("nan"))
    chart_data = chart_data.dropna(subset=["ElapsedSec", "Alt"]).sort_values("ElapsedSec")
    if chart_data.empty:
        st.warning("No valid altitude measurements were found.")
        return

    st.subheader("📈 Altitude vs. Time")
    fig = px.line(
        chart_data,
        x="ElapsedSec",
        y="Alt",
        labels={
            "ElapsedSec": "Elapsed Recording Time (seconds)",
            "Alt": "CTUN Altitude (metres)",
        },
        title="Recorded CTUN Altitude",
    )
    fig.update_layout(height=450, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "CTUN altitude uses the common recording-time origin. "
        "Altitude variation alone does not confirm airborne flight."
    )


def render_gps_speed_chart(log_path):
    """Plot GPS ground speed from quality-filtered fixes on the shared timeline."""
    telemetry, origin_sec = _load_synchronized_telemetry(log_path)
    gps = telemetry.get("GPS")

    st.subheader("📡 GPS Ground Speed vs. Time")
    if gps is None or gps.empty:
        st.warning("GPS telemetry is unavailable.")
        return
    if origin_sec is None or not {"TimeUS", "Status", "Spd"}.issubset(gps.columns):
        st.warning("Required GPS fields are missing.")
        return

    chart_data = _add_elapsed_seconds(gps[["TimeUS", "Status", "Spd"]], origin_sec)
    for column in ("Status", "Spd"):
        chart_data[column] = pd.to_numeric(chart_data[column], errors="coerce")
    chart_data = chart_data.replace([float("inf"), float("-inf")], float("nan"))
    chart_data = chart_data.dropna(subset=["ElapsedSec", "Status", "Spd"]).sort_values("ElapsedSec")

    valid_data = chart_data.loc[
        (chart_data["Status"] >= 3) & (chart_data["Spd"] >= 0)
    ].copy()
    st.caption(f"Usable GPS speed samples: {len(valid_data):,} of {len(gps):,}")
    if valid_data.empty:
        st.warning("No GPS samples passed the fix-quality checks.")
        return

    fig = px.line(
        valid_data,
        x="ElapsedSec",
        y="Spd",
        labels={
            "ElapsedSec": "Elapsed Recording Time (seconds)",
            "Spd": "GPS Ground Speed (m/s)",
        },
        title="Recorded GPS Ground Speed",
    )
    fig.update_layout(height=450, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Only GPS samples with a 3D-or-better fix and non-negative speed "
        "are displayed. Missing samples are not zero-speed measurements."
    )


def render_motor_pwm_chart(log_path):
    """Visualize selected RCOU output channels on the shared timeline."""
    st.subheader("⚙️ Motor PWM Outputs vs. Time")
    telemetry, origin_sec = _load_synchronized_telemetry(log_path)
    rcou = telemetry.get("RCOU")
    if rcou is None or rcou.empty:
        st.warning("RCOU telemetry is unavailable.")
        return
    if origin_sec is None or "TimeUS" not in rcou.columns:
        st.warning("RCOU timestamps are missing.")
        return

    channels = [f"C{i}" for i in range(1, 15) if f"C{i}" in rcou.columns]
    if not channels:
        st.warning("No RCOU output channels were found.")
        return

    default_channels = [ch for ch in ("C1", "C2", "C3", "C4") if ch in channels]
    selected_channels = st.multiselect(
        "Select output channels",
        options=channels,
        default=default_channels,
        key="motor_pwm_channels",
    )
    if not selected_channels:
        st.info("Select at least one channel to display.")
        return

    chart_data = _add_elapsed_seconds(rcou[["TimeUS", *selected_channels]], origin_sec)
    for channel in selected_channels:
        chart_data[channel] = pd.to_numeric(chart_data[channel], errors="coerce")
    chart_data = chart_data.replace([float("inf"), float("-inf")], float("nan"))
    chart_data = chart_data.dropna(subset=["ElapsedSec"]).sort_values("ElapsedSec")
    if chart_data.empty:
        st.warning("No valid RCOU timestamps were found.")
        return

    long_data = chart_data.melt(
        id_vars=["ElapsedSec"],
        value_vars=selected_channels,
        var_name="Channel",
        value_name="PWM",
    ).dropna(subset=["PWM"])
    if long_data.empty:
        st.warning("No valid output values were found.")
        return

    fig = px.line(
        long_data,
        x="ElapsedSec",
        y="PWM",
        color="Channel",
        labels={
            "ElapsedSec": "Elapsed Recording Time (seconds)",
            "PWM": "Output PWM (µs)",
        },
        title="Recorded RCOU Output Channels",
    )
    fig.update_layout(height=500, hovermode="x unified", legend_title_text="Channels")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "RCOU channels are commanded controller outputs, not measured motor "
        "RPM or thrust. Channel-to-motor mapping depends on UAV configuration."
    )
