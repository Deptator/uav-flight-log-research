"""Experimental UAV flight candidate classification and armed-session reporting.

Labels describe telemetry evidence, not confirmed airborne flight.
"""

import pandas as pd


def classify_activity_segments(
    evidence_df,
    quality_df,
    min_alt_range_m=2.0,
    min_speed95_mps=0.5,
):
    """Classify activity segments using altitude, GPS and quality evidence."""
    keys = ["Session", "Segment"]
    required_evidence = {"Session", "Segment", "DurationSec", "AltRange", "Speed95"}
    required_quality = {"Session", "Segment", "QualityWarning", "InsufficientData"}

    if not required_evidence.issubset(evidence_df.columns):
        raise ValueError(f"Missing evidence columns: {required_evidence - set(evidence_df.columns)}")
    if not required_quality.issubset(quality_df.columns):
        raise ValueError(f"Missing quality columns: {required_quality - set(quality_df.columns)}")
    if min_alt_range_m < 0 or min_speed95_mps < 0:
        raise ValueError("Thresholds must be non-negative.")
    if evidence_df.duplicated(keys).any():
        raise ValueError("Duplicate segment keys in evidence data.")
    if quality_df.duplicated(keys).any():
        raise ValueError("Duplicate segment keys in quality data.")

    data = evidence_df.merge(
        quality_df[keys + ["QualityWarning", "InsufficientData"]],
        on=keys,
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    if (data["_merge"] != "both").any():
        raise ValueError("Missing quality records for some segments.")
    data = data.drop(columns="_merge")

    classifications = []
    explanations = []
    for _, row in data.iterrows():
        quality_warning = row["QualityWarning"]
        insufficient = row["InsufficientData"]
        if pd.isna(quality_warning) or pd.isna(insufficient):
            classification = "REVIEW_REQUIRED"
            explanation = "Missing quality assessment."
        elif bool(insufficient):
            classification = "REVIEW_REQUIRED"
            explanation = "Insufficient altitude-quality data."
        elif bool(quality_warning):
            classification = "REVIEW_REQUIRED"
            explanation = "Altitude-source disagreement detected."
        elif pd.isna(row["AltRange"]) or pd.isna(row["Speed95"]):
            classification = "REVIEW_REQUIRED"
            explanation = "Missing altitude or GPS evidence."
        else:
            altitude_support = row["AltRange"] >= min_alt_range_m
            motion_support = row["Speed95"] >= min_speed95_mps
            if altitude_support and motion_support:
                classification = "STRONG_CANDIDATE"
                explanation = "Sustained output with altitude and GPS evidence."
            else:
                classification = "REVIEW_REQUIRED"
                explanation = (
                    "Altitude and GPS evidence do not both meet thresholds."
                )
        classifications.append(classification)
        explanations.append(explanation)

    data["Classification"] = classifications
    data["Explanation"] = explanations
    return data


def build_session_report(armed_sessions_df, session_detection_df, classified_segments_df):
    """One report record per complete armed session.

    Session-level insufficient RCOU coverage overrides segment-level labels,
    but does not discard the observed segments themselves.
    """
    required_detection = {
        "Session", "ActivityStatus", "ActivitySegments", "TotalActivitySec", "ActivityRatio"
    }
    required_classification = {"Session", "Segment", "Classification"}

    if not required_detection.issubset(session_detection_df.columns):
        missing = required_detection - set(session_detection_df.columns)
        raise ValueError(f"Missing session-detection columns: {missing}")
    if not required_classification.issubset(classified_segments_df.columns):
        missing = required_classification - set(classified_segments_df.columns)
        raise ValueError(f"Missing segment-classification columns: {missing}")

    sessions = armed_sessions_df.reset_index().copy()
    if "Session" not in sessions.columns:
        raise ValueError("Armed sessions must have a Session index.")
    if sessions["Session"].duplicated().any():
        raise ValueError("Duplicate armed-session IDs.")
    if session_detection_df["Session"].duplicated().any():
        raise ValueError("Duplicate session-detection records.")
    if classified_segments_df.duplicated(["Session", "Segment"]).any():
        raise ValueError("Duplicate classified segments.")

    valid_labels = {"STRONG_CANDIDATE", "REVIEW_REQUIRED"}
    if not classified_segments_df["Classification"].isin(valid_labels).all():
        raise ValueError("Unknown segment-classification label.")

    # Preserve the original segment priority (review takes precedence).
    def summarize(group):
        labels = set(group.dropna())
        if "REVIEW_REQUIRED" in labels:
            return "REVIEW_REQUIRED"
        if "STRONG_CANDIDATE" in labels:
            return "STRONG_CANDIDATE"
        return "REVIEW_REQUIRED"

    session_labels = (
        classified_segments_df.groupby("Session")["Classification"]
        .apply(summarize)
        .reset_index(name="SessionClassification")
    )
    report = (
        sessions.merge(session_detection_df, on="Session", how="left", validate="one_to_one")
        .merge(session_labels, on="Session", how="left", validate="one_to_one")
    )

    if report["ActivitySegments"].isna().any():
        raise ValueError("Some armed sessions have no detection summary.")

    actual_counts = (
        classified_segments_df.groupby("Session").size()
        .rename("ClassifiedCount").reset_index()
    )
    report = report.merge(actual_counts, on="Session", how="left", validate="one_to_one")
    report["ClassifiedCount"] = report["ClassifiedCount"].fillna(0).astype(int)
    if (report["ActivitySegments"] != report["ClassifiedCount"]).any():
        raise ValueError("Detected and classified segment counts do not match.")

    valid_statuses = {"INSUFFICIENT_DATA", "NO_ACTIVITY", "ACTIVITY_DETECTED"}
    if not report["ActivityStatus"].isin(valid_statuses).all():
        raise ValueError("Unknown or missing activity status.")

    missing_motor_data = report["ActivityStatus"] == "INSUFFICIENT_DATA"
    no_activity = report["ActivityStatus"] == "NO_ACTIVITY"
    activity_detected = report["ActivityStatus"] == "ACTIVITY_DETECTED"

    # NO_ACTIVITY implies zero detected segments. INSUFFICIENT_DATA does not:
    # partial telemetry can contain real observed activity segments.
    if (no_activity & report["ActivitySegments"].ne(0)).any():
        raise ValueError("NO_ACTIVITY conflicts with detected segments.")
    if (activity_detected & report["ActivitySegments"].le(0)).any():
        raise ValueError("ACTIVITY_DETECTED requires at least one segment.")
    if (activity_detected & report["SessionClassification"].isna()).any():
        raise ValueError("Activity detected but segment classifications are missing.")

    # When no segments were classified, pandas may create this column as float64
    # (all NaN). Explicit object dtype makes string label assignment reliable.
    report["SessionClassification"] = report["SessionClassification"].astype(object)

    # Insufficient coverage overrides even strong individual segment evidence.
    report.loc[missing_motor_data, "SessionClassification"] = "REVIEW_REQUIRED"
    report.loc[no_activity, "SessionClassification"] = "LOW_ACTIVITY"

    return (
        report.drop(columns=["ClassifiedCount"])
        .sort_values("Session")
        .reset_index(drop=True)
    )
