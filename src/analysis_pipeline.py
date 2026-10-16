"""
Automated UAV Flight Log Analysis Pipeline.

Coordinates existing parsing, activity-detection,
telemetry-quality and classification modules.

Flight classifications are experimental and do not
establish confirmed airborne flight.
"""

from pathlib import Path

import pandas as pd
import numpy as np

from src.log_parser import parse_flight_log
from src.flight_detection import (
    prepare_motor_data,
    detect_motor_activity
)
from src.telemetry_quality import compare_altitude_sources
from src.flight_classification import (
    classify_activity_segments,
    build_session_report
)


REQUIRED_MESSAGE_TYPES = [
    "ARM",
    "RCOU",
    "CTUN",
    "GPS",
    "BARO",
    "MODE"
]


def validate_log_path(log_path):
    """
    Validate the input flight-log path.

    Returns
    -------
    pathlib.Path
        Resolved path to an existing BIN flight log.
    """

    path = Path(log_path).expanduser().resolve()

    if not path.is_file():
        raise FileNotFoundError(
            f"Flight log not found: {path}"
        )

    if path.suffix.lower() != ".bin":
        raise ValueError(
            "Expected an ArduPilot .bin flight log."
        )

    return path


def reconstruct_armed_sessions(arm_df):
    """
    Reconstruct complete ARM-to-DISARM intervals.

    Parameters
    ----------
    arm_df : pandas.DataFrame
        ARM telemetry containing TimeUS and ArmState.

    Returns
    -------
    pandas.DataFrame
        Complete armed intervals with:
        Session, StartSec, EndSec and DurationSec.

    Notes
    -----
    Incomplete intervals are not classified as flights.
    """

    required_columns = {"TimeUS", "ArmState"}

    missing = required_columns - set(arm_df.columns)

    if missing:
        raise ValueError(
            f"Missing ARM columns: {sorted(missing)}"
        )

    events = arm_df[["TimeUS", "ArmState"]].copy()

    events["TimeSec"] = (
        pd.to_numeric(events["TimeUS"], errors="coerce")
        / 1_000_000
    )

    events["ArmState"] = pd.to_numeric(
        events["ArmState"],
        errors="coerce"
    )

    events = (
        events.dropna(subset=["TimeSec", "ArmState"])
        .sort_values("TimeSec")
        .reset_index(drop=True)
    )

    intervals = []
    arm_start = None

    for _, event in events.iterrows():

        timestamp = float(event["TimeSec"])
        state = int(event["ArmState"])

        if state == 1:

            if arm_start is None:
                arm_start = timestamp

            else:
                print(
                    "Warning: repeated ARM event at "
                    f"{timestamp:.2f}s"
                )

        elif state == 0:

            if arm_start is not None:

                intervals.append({
                    "StartSec": arm_start,
                    "EndSec": timestamp,
                    "DurationSec": timestamp - arm_start
                })

                arm_start = None

            else:
                print(
                    "Warning: DISARM without ARM at "
                    f"{timestamp:.2f}s"
                )

        else:
            print(
                f"Warning: unexpected ARM state {state}"
            )

    if arm_start is not None:
        print(
            "Warning: final ARM interval is incomplete."
        )

    sessions = pd.DataFrame(
        intervals,
        columns=["StartSec", "EndSec", "DurationSec"]
    )

    # Match the session-index format used by our
    # existing reporting module.
    sessions.index = pd.Index(
        range(1, len(sessions) + 1),
        name="Session"
    )

    return sessions

def analyze_motor_activity(
    rcou_df,
    armed_sessions_df,
    pwm_threshold=1350,
    min_duration_sec=3.0,
    max_gap_sec=1.0,
    max_sample_gap_sec=0.5,
    min_coverage_ratio=0.90
):
    """Detect output segments and assess per-session RCOU time coverage.

    Coverage is a timestamp-continuity proxy, not a guarantee of
    valid individual PWM channel values. Segments are retained even
    when overall session coverage is insufficient.
    """
    if not 0 <= min_coverage_ratio <= 1:
        raise ValueError("min_coverage_ratio must be between 0 and 1.")
    if max_sample_gap_sec <= 0:
        raise ValueError("max_sample_gap_sec must be positive.")

    prepared_motor = prepare_motor_data(rcou_df)
    activity_rows = []
    summary_rows = []

    for session_id, session in armed_sessions_df.iterrows():
        start = session["StartSec"]
        end = session["EndSec"]
        armed_duration = session["DurationSec"]

        session_motor = prepared_motor[
            prepared_motor["TimeSec"].between(start, end)
        ]
        motor_samples = len(session_motor)
        motor_data_available = motor_samples > 0

        timestamps = np.sort(
            pd.to_numeric(
                session_motor["TimeSec"], errors="coerce"
            ).dropna().unique()
        )
        gaps = np.diff(timestamps)
        covered_duration = float(
            gaps[(gaps > 0) & (gaps <= max_sample_gap_sec)].sum()
        )
        coverage_ratio = (
            min(1.0, covered_duration / armed_duration)
            if armed_duration > 0 else np.nan
        )
        coverage_sufficient = bool(
            np.isfinite(coverage_ratio)
            and coverage_ratio >= min_coverage_ratio
        )

        detected = detect_motor_activity(
            session_motor,
            pwm_threshold=pwm_threshold,
            min_duration_sec=min_duration_sec,
            max_gap_sec=max_gap_sec,
            max_sample_gap_sec=max_sample_gap_sec
        )

        for segment_number, (_, segment) in enumerate(
            detected.iterrows(), start=1
        ):
            activity_rows.append({
                "Session": session_id,
                "Segment": segment_number,
                "StartSec": segment["StartSec"],
                "EndSec": segment["EndSec"],
                "DurationSec": segment["DurationSec"],
                "MeanPWM": segment["MeanPWM"]
            })

        total_activity = detected["DurationSec"].sum()

        if not coverage_sufficient:
            activity_status = "INSUFFICIENT_DATA"
        elif len(detected) > 0:
            activity_status = "ACTIVITY_DETECTED"
        else:
            activity_status = "NO_ACTIVITY"

        summary_rows.append({
            "Session": session_id,
            "ArmedDurationSec": armed_duration,
            "MotorSamples": motor_samples,
            "MotorDataAvailable": motor_data_available,
            "CoveredDurationSec": covered_duration,
            "CoverageRatio": coverage_ratio,
            "CoverageSufficient": coverage_sufficient,
            "ActivityStatus": activity_status,
            "ActivitySegments": len(detected),
            "TotalActivitySec": (
                total_activity if coverage_sufficient else np.nan
            ),
            "ActivityRatio": (
                total_activity / armed_duration
                if coverage_sufficient and armed_duration > 0 else np.nan
            )
        })

    activity_segments_df = pd.DataFrame(activity_rows, columns=[
        "Session", "Segment", "StartSec", "EndSec",
        "DurationSec", "MeanPWM"
    ])
    session_detection_df = pd.DataFrame(summary_rows, columns=[
        "Session", "ArmedDurationSec", "MotorSamples",
        "MotorDataAvailable", "CoveredDurationSec", "CoverageRatio",
        "CoverageSufficient", "ActivityStatus", "ActivitySegments",
        "TotalActivitySec", "ActivityRatio"
    ])
    return activity_segments_df, session_detection_df


def extract_segment_evidence(
    ctun_df,
    gps_df,
    activity_segments_df
):
    """
    Extract altitude and GPS evidence for motor-activity
    segments.

    Only GPS samples with a 3D-or-better fix and a
    non-negative ground-speed measurement are used.

    Returns
    -------
    pandas.DataFrame
        One telemetry-evidence record per activity segment.
    """

    required_ctun = {"TimeUS", "Alt"}
    required_gps = {
        "TimeUS", "Status", "Spd"
    }
    required_segments = {
        "Session", "Segment", "StartSec",
        "EndSec", "DurationSec", "MeanPWM"
    }

    for name, dataframe, required in [
        ("CTUN", ctun_df, required_ctun),
        ("GPS", gps_df, required_gps),
        ("Activity segments", activity_segments_df, required_segments)
    ]:
        missing = required - set(dataframe.columns)

        if missing:
            raise ValueError(
                f"Missing {name} columns: {sorted(missing)}"
            )

    # Prepare estimated altitude
    altitude_data = ctun_df[["TimeUS", "Alt"]].copy()

    altitude_data["TimeSec"] = (
        pd.to_numeric(
            altitude_data["TimeUS"],
            errors="coerce"
        ) / 1_000_000
    )

    altitude_data["Alt"] = pd.to_numeric(
        altitude_data["Alt"],
        errors="coerce"
    )

    altitude_data = (
        altitude_data
        .dropna(subset=["TimeSec"])
        .sort_values("TimeSec")
    )

    # Prepare GPS telemetry
    gps_data = gps_df[
        ["TimeUS", "Status", "Spd"]
    ].copy()

    gps_data["TimeSec"] = (
        pd.to_numeric(
            gps_data["TimeUS"],
            errors="coerce"
        ) / 1_000_000
    )

    for column in ["Status", "Spd"]:
        gps_data[column] = pd.to_numeric(
            gps_data[column],
            errors="coerce"
        )

    gps_data = gps_data[
        (gps_data["Status"] >= 3)
        & (gps_data["Spd"].notna())
        & (gps_data["Spd"] >= 0)
    ].sort_values("TimeSec")

    evidence_rows = []

    for _, segment in activity_segments_df.iterrows():

        start = segment["StartSec"]
        end = segment["EndSec"]

        altitude_segment = (
            altitude_data[
                altitude_data["TimeSec"].between(start, end)
            ]
            .sort_values("TimeSec")
        )

        gps_segment = gps_data[
            gps_data["TimeSec"].between(start, end)
        ]

        altitude = altitude_segment["Alt"].dropna()
        speed = gps_segment["Spd"].dropna()

        evidence_rows.append({
            "Session": int(segment["Session"]),
            "Segment": int(segment["Segment"]),
            "DurationSec": segment["DurationSec"],
            "MeanPWM": segment["MeanPWM"],
            "AltStart": (
                altitude.iloc[0]
                if not altitude.empty else np.nan
            ),
            "AltEnd": (
                altitude.iloc[-1]
                if not altitude.empty else np.nan
            ),
            "AltRange": (
                altitude.max() - altitude.min()
                if not altitude.empty else np.nan
            ),
            "MeanSpeed": speed.mean(),
            "MaxSpeed": speed.max(),
            "Speed95": speed.quantile(0.95),
            "AltSamples": len(altitude),
            "GPSSamples": len(speed)
        })

    columns = [
        "Session", "Segment", "DurationSec",
        "MeanPWM", "AltStart", "AltEnd",
        "AltRange", "MeanSpeed", "MaxSpeed",
        "Speed95", "AltSamples", "GPSSamples"
    ]

    return pd.DataFrame(evidence_rows, columns=columns)



def analyze_altitude_quality(
    ctun_df,
    baro_df,
    activity_segments_df,
    tolerance_sec=0.15,
    warning_threshold_m=2.0
):
    """
    Evaluate CTUN-BARO altitude agreement for each
    detected motor-activity segment.

    Returns
    -------
    pandas.DataFrame
        One quality-assessment record per segment.
    """

    required_segments = {
        "Session", "Segment", "StartSec", "EndSec"
    }

    missing = required_segments - set(activity_segments_df.columns)

    if missing:
        raise ValueError(
            f"Missing activity segment columns: {sorted(missing)}"
        )

    # Prepare timestamps and altitude values once
    def prepare_altitude(data, source_name):
        required = {"TimeUS", "Alt"}

        missing = required - set(data.columns)

        if missing:
            raise ValueError(
                f"Missing {source_name} columns: {sorted(missing)}"
            )

        prepared = data[["TimeUS", "Alt"]].copy()

        prepared["TimeSec"] = (
            pd.to_numeric(prepared["TimeUS"], errors="coerce")
            / 1_000_000
        )

        prepared["Alt"] = pd.to_numeric(
            prepared["Alt"], errors="coerce"
        )

        return prepared[["TimeSec", "Alt"]]

    prepared_ctun = prepare_altitude(ctun_df, "CTUN")
    prepared_baro = prepare_altitude(baro_df, "BARO")

    quality_rows = []

    for _, segment in activity_segments_df.iterrows():

        _, quality = compare_altitude_sources(
            prepared_ctun,
            prepared_baro,
            start_sec=segment["StartSec"],
            end_sec=segment["EndSec"],
            tolerance_sec=tolerance_sec,
            warning_threshold_m=warning_threshold_m
        )

        quality_rows.append({
            "Session": int(segment["Session"]),
            "Segment": int(segment["Segment"]),
            "MatchedSamples": quality["MatchedSamples"],
            "MedianAbsDiff": quality["MedianAbsDifference"],
            "P95AbsDiff": quality["P95AbsDifference"],
            "MaxAbsDiff": quality["MaxAbsDifference"],
            "WarningSamples": quality["WarningSamples"],
            "QualityWarning": quality["QualityWarning"],
            "InsufficientData": quality["InsufficientData"]
        })

    columns = [
        "Session",
        "Segment",
        "MatchedSamples",
        "MedianAbsDiff",
        "P95AbsDiff",
        "MaxAbsDiff",
        "WarningSamples",
        "QualityWarning",
        "InsufficientData"
    ]

    return pd.DataFrame(quality_rows, columns=columns)


def generate_flight_reports(
    armed_sessions_df,
    session_detection_df,
    segment_evidence_df,
    segment_quality_df,
    min_alt_range_m=2.0,
    min_speed95_mps=0.5
):
    """
    Generate segment classifications and session reports.

    Classification is based on experimental telemetry
    thresholds and does not confirm airborne flight.

    Returns
    -------
    tuple
        (classified_segments_df, session_report_df)
    """

    # Classify motor-activity segments
    classified_segments_df = classify_activity_segments(
        segment_evidence_df,
        segment_quality_df,
        min_alt_range_m=min_alt_range_m,
        min_speed95_mps=min_speed95_mps
    )

    # Generate one report entry per armed session
    session_report_df = build_session_report(
        armed_sessions_df,
        session_detection_df,
        classified_segments_df
    )

    return classified_segments_df, session_report_df


def analyze_flight_log(
    log_path,
    pwm_threshold=1350,
    min_duration_sec=3.0,
    max_gap_sec=1.0,
    max_sample_gap_sec=0.5,
    altitude_tolerance_sec=0.15,
    altitude_warning_m=2.0,
    min_alt_range_m=2.0,
    min_speed95_mps=0.5,
    min_coverage_ratio=0.90
):
    """
    Run the complete experimental UAV flight-analysis pipeline.

    Parameters
    ----------
    log_path : str or pathlib.Path
        Path to an ArduPilot BIN flight log.

    Returns
    -------
    dict
        Analysis results containing:
        - LogPath
        - ArmedSessions
        - ActivitySegments
        - SessionDetection
        - SegmentEvidence
        - AltitudeQuality
        - ClassifiedSegments
        - SessionReport

    Notes
    -----
    Classifications are experimental research labels,
    not confirmed airborne-flight events.
    """

    # 1. Validate the input file
    validated_path = validate_log_path(log_path)

    # 2. Parse the required telemetry messages
    telemetry = parse_flight_log(
        validated_path,
        message_types=REQUIRED_MESSAGE_TYPES
    )

    # 3. Verify required message types are present
    required = {"ARM", "RCOU", "CTUN", "BARO"}

    missing = required - set(telemetry.keys())

    if missing:
        raise ValueError(
            "Missing required telemetry messages: "
            f"{sorted(missing)}"
        )

    # GPS is optional: preserve missing speed as NaN instead of zero.
    # The existing classifier sends segments without GPS evidence to review.
    if "GPS" not in telemetry or telemetry["GPS"] is None:
        gps_df = pd.DataFrame(columns=["TimeUS", "Status", "Spd"])
    else:
        gps_df = telemetry["GPS"]

    # 4. Reconstruct armed sessions
    armed_sessions = reconstruct_armed_sessions(
        telemetry["ARM"]
    )

    # 5. Detect sustained motor activity
    activity_segments, session_detection = (
        analyze_motor_activity(
            telemetry["RCOU"],
            armed_sessions,
            pwm_threshold=pwm_threshold,
            min_duration_sec=min_duration_sec,
            max_gap_sec=max_gap_sec,
            max_sample_gap_sec=max_sample_gap_sec,
            min_coverage_ratio=min_coverage_ratio
        )
    )

    # 6. Extract altitude and GPS evidence
    segment_evidence = extract_segment_evidence(
        telemetry["CTUN"],
        gps_df,
        activity_segments
    )

    # 7. Evaluate CTUN-BARO altitude agreement
    altitude_quality = analyze_altitude_quality(
        telemetry["CTUN"],
        telemetry["BARO"],
        activity_segments,
        tolerance_sec=altitude_tolerance_sec,
        warning_threshold_m=altitude_warning_m
    )

    # 8. Classify activity and generate session reports
    classified_segments, session_report = (
        generate_flight_reports(
            armed_sessions,
            session_detection,
            segment_evidence,
            altitude_quality,
            min_alt_range_m=min_alt_range_m,
            min_speed95_mps=min_speed95_mps
        )
    )

    return {
        "LogPath": str(validated_path),
        "ArmedSessions": armed_sessions,
        "ActivitySegments": activity_segments,
        "SessionDetection": session_detection,
        "SegmentEvidence": segment_evidence,
        "AltitudeQuality": altitude_quality,
        "ClassifiedSegments": classified_segments,
        "SessionReport": session_report
    }



