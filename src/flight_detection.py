
"""Utilities for identifying sustained UAV motor-output activity.

These functions detect activity in candidate motor channels.
They do not independently establish that a UAV was airborne.
"""

import pandas as pd


def prepare_motor_data(rcou_df, channels=("C1", "C2", "C3", "C4")):
    """
    Prepare candidate motor-output telemetry for analysis.

    Parameters
    ----------
    rcou_df : pandas.DataFrame
        RCOU telemetry containing TimeUS and output channels.

    channels : tuple
        Candidate motor-output channel names.

    Returns
    -------
    pandas.DataFrame
        Time-sorted telemetry with TimeSec and MeanPWM columns.
    """

    required_columns = ["TimeUS", *channels]

    missing = [
        column for column in required_columns
        if column not in rcou_df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required RCOU columns: {missing}"
        )

    data = rcou_df.copy()

    data["TimeSec"] = (
        pd.to_numeric(data["TimeUS"], errors="coerce")
        / 1_000_000
    )

    for channel in channels:
        data[channel] = pd.to_numeric(
            data[channel],
            errors="coerce"
        )

    data["MeanPWM"] = data[list(channels)].mean(
        axis=1,
        skipna=False
    )

    data = (
        data.dropna(subset=["TimeSec", "MeanPWM"])
        .sort_values("TimeSec")
        .reset_index(drop=True)
    )

    return data


def detect_motor_activity(
    motor_df,
    pwm_threshold=1350,
    min_duration_sec=3.0,
    max_gap_sec=1.0,
    max_sample_gap_sec=0.5
):
    """
    Detect sustained high-output activity periods.

    Short low-output interruptions may be merged, but
    timestamp gaps larger than max_sample_gap_sec
    always break continuity.

    Returns
    -------
    pandas.DataFrame
        StartSec, EndSec, DurationSec and MeanPWM.
    """

    if (
        min_duration_sec < 0
        or max_gap_sec < 0
        or max_sample_gap_sec <= 0
    ):
        raise ValueError("Invalid duration or gap parameter.")

    required = {"TimeSec", "MeanPWM"}

    if not required.issubset(motor_df.columns):
        raise ValueError(
            "Motor data must contain TimeSec and MeanPWM."
        )

    data = motor_df[["TimeSec", "MeanPWM"]].copy()

    for column in ["TimeSec", "MeanPWM"]:
        data[column] = pd.to_numeric(
            data[column], errors="coerce"
        )

    data = (
        data.dropna()
        .sort_values("TimeSec")
        .reset_index(drop=True)
    )

    columns = [
        "StartSec", "EndSec", "DurationSec", "MeanPWM"
    ]

    if data.empty:
        return pd.DataFrame(columns=columns)

    # Split the data at missing or widely spaced timestamps.
    time_gap = data["TimeSec"].diff()
    block_id = (
        time_gap.gt(max_sample_gap_sec)
        | time_gap.le(0)
    ).cumsum()

    detected = []

    for _, block in data.groupby(block_id):

        block = block.reset_index(drop=True)

        high = block["MeanPWM"] > pwm_threshold

        # Identify consecutive high-output runs.
        run_id = high.ne(high.shift()).cumsum()

        runs = []

        for _, run in block.groupby(run_id):

            if not (run["MeanPWM"].iloc[0] > pwm_threshold):
                continue

            runs.append([
                float(run["TimeSec"].iloc[0]),
                float(run["TimeSec"].iloc[-1])
            ])

        # Merge nearby runs inside this continuous block.
        merged = []

        for start, end in runs:

            if merged and start - merged[-1][1] <= max_gap_sec:
                merged[-1][1] = end
            else:
                merged.append([start, end])

        for start, end in merged:

            duration = end - start

            if duration < min_duration_sec:
                continue

            window = block[
                block["TimeSec"].between(start, end)
            ]

            detected.append({
                "StartSec": start,
                "EndSec": end,
                "DurationSec": duration,
                "MeanPWM": window["MeanPWM"].mean()
            })

    return pd.DataFrame(detected, columns=columns)





    
