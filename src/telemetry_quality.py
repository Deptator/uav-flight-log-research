
"""Telemetry quality checks for UAV flight-log analysis."""

import numpy as np
import pandas as pd


def compare_altitude_sources(
    ctun_df,
    baro_df,
    start_sec,
    end_sec,
    tolerance_sec=0.15,
    warning_threshold_m=2.0
):
    """
    Compare relative CTUN and BARO altitude measurements.

    Both inputs must contain TimeSec and Alt columns.

    Returns
    -------
    tuple
        (comparison_df, quality_summary)
    """

    if start_sec >= end_sec:
        raise ValueError("start_sec must be less than end_sec.")

    if tolerance_sec <= 0 or warning_threshold_m < 0:
        raise ValueError("Invalid tolerance or warning threshold.")

    def prepare(data, altitude_name):
        required = {"TimeSec", "Alt"}

        if not required.issubset(data.columns):
            raise ValueError(
                f"Missing required columns: {required - set(data.columns)}"
            )

        result = data[["TimeSec", "Alt"]].copy()

        result["TimeSec"] = pd.to_numeric(
            result["TimeSec"], errors="coerce"
        )

        result["Alt"] = pd.to_numeric(
            result["Alt"], errors="coerce"
        )

        return (
            result[
                result["TimeSec"].between(start_sec, end_sec)
            ]
            .dropna()
            .rename(columns={"Alt": altitude_name})
            .sort_values("TimeSec")
            .reset_index(drop=True)
        )

    ctun = prepare(ctun_df, "CTUN_Alt")
    baro = prepare(baro_df, "BARO_Alt")

    summary = {
        "MatchedSamples": 0,
        "MedianAbsDifference": np.nan,
        "P95AbsDifference": np.nan,
        "MaxAbsDifference": np.nan,
        "WarningSamples": 0,
        "FirstWarningSec": np.nan,
        "QualityWarning": False,
        "InsufficientData": True
    }

    empty_columns = [
        "TimeSec", "CTUN_Alt", "BARO_Alt",
        "CTUN_Rel", "BARO_Rel", "AltitudeDifference"
    ]

    if ctun.empty or baro.empty:
        return pd.DataFrame(columns=empty_columns), summary

    comparison = pd.merge_asof(
        ctun,
        baro,
        on="TimeSec",
        direction="nearest",
        tolerance=tolerance_sec
    ).dropna(subset=["CTUN_Alt", "BARO_Alt"])

    comparison = comparison.reset_index(drop=True)

    if len(comparison) < 2:
        return comparison, summary

    comparison["CTUN_Rel"] = (
        comparison["CTUN_Alt"] - comparison["CTUN_Alt"].iloc[0]
    )

    comparison["BARO_Rel"] = (
        comparison["BARO_Alt"] - comparison["BARO_Alt"].iloc[0]
    )

    comparison["AltitudeDifference"] = (
        comparison["CTUN_Rel"] - comparison["BARO_Rel"]
    )

    abs_diff = comparison["AltitudeDifference"].abs()

    warnings = comparison[
        abs_diff > warning_threshold_m
    ]

    summary.update({
        "MatchedSamples": len(comparison),
        "MedianAbsDifference": abs_diff.median(),
        "P95AbsDifference": abs_diff.quantile(0.95),
        "MaxAbsDifference": abs_diff.max(),
        "WarningSamples": len(warnings),
        "FirstWarningSec": (
            warnings["TimeSec"].iloc[0]
            if not warnings.empty else np.nan
        ),
        "QualityWarning": not warnings.empty,
        "InsufficientData": False
    })

    return comparison, summary
