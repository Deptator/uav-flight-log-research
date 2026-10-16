"""Descriptive cross-log statistics for reconstructed UAV armed sessions.

Inputs are session-level exports, not ground-truth flight labels. Aggregations
preserve recording identity, and missing numeric data is not silently zeroed.
"""

import numpy as np
import pandas as pd

METRICS = ("ArmedDurationSec", "ActivityRatio", "CoverageRatio", "TotalActivitySec")
LABELS = ("LOW_ACTIVITY", "REVIEW_REQUIRED", "STRONG_CANDIDATE")
REQUIRED = {"LogFile", "Session", "SessionClassification", *METRICS}


def analyze_session_statistics(sessions):
    """Return Baseline, Classification, Recordings, Concentration, and Summary.

    Raises ValueError for incomplete identifiers, duplicates, invalid metric
    values, or inconsistent durations/ratios. No statistical significance or
    aircraft flight status is inferred by these descriptive summaries.
    """
    if not isinstance(sessions, pd.DataFrame):
        raise TypeError("sessions must be a pandas DataFrame")
    missing = REQUIRED.difference(sessions.columns)
    if missing:
        raise ValueError(f"Missing session columns: {sorted(missing)}")
    if sessions.empty:
        raise ValueError("Session table is empty")
    if sessions[["LogFile", "Session", "SessionClassification"]].isna().any().any():
        raise ValueError("Missing recording, session, or classification identity")
    if sessions.duplicated(["LogFile", "Session"]).any():
        raise ValueError("Duplicate (LogFile, Session) identities")
    if not sessions["SessionClassification"].isin(LABELS).all():
        raise ValueError("Unrecognized classification labels")

    data = sessions.copy()
    for metric in METRICS:
        data[metric] = pd.to_numeric(data[metric], errors="raise")
        values = data[metric].dropna()
        if not np.isfinite(values).all():
            raise ValueError(f"Infinite values in {metric}")
        if (values < 0).any():
            raise ValueError(f"Negative {metric}")
    if (data["ArmedDurationSec"].dropna() <= 0).any():
        raise ValueError("Armed duration must be positive")
    for ratio in ("ActivityRatio", "CoverageRatio"):
        if (data[ratio].dropna() > 1 + 1e-6).any():
            raise ValueError(f"{ratio} cannot exceed 1")

    baseline = data[list(METRICS)].describe().T.reset_index(names="Metric")

    grouped = data.groupby("SessionClassification", sort=False)
    classification = grouped.agg(
        Sessions=("Session", "size"),
        MeanDurationSec=("ArmedDurationSec", "mean"),
        MedianDurationSec=("ArmedDurationSec", "median"),
        MeanActivityRatio=("ActivityRatio", "mean"),
        MedianActivityRatio=("ActivityRatio", "median"),
        MeanActivitySec=("TotalActivitySec", "mean"),
        MeanCoverageRatio=("CoverageRatio", "mean"),
        UniqueRecordings=("LogFile", "nunique"),
    ).reset_index()
    classification["Percentage"] = classification["Sessions"] / len(data) * 100
    classification = classification.sort_values("SessionClassification").reset_index(drop=True)

    recordings = data.groupby("LogFile", sort=True).agg(
        ArmedSessions=("Session", "size"),
        TotalArmedDurationSec=("ArmedDurationSec", "sum"),
        MeanArmedDurationSec=("ArmedDurationSec", "mean"),
        TotalActivitySec=("TotalActivitySec", lambda x: x.sum(min_count=1)),
        MeanActivityRatio=("ActivityRatio", "mean"),
        MeanCoverageRatio=("CoverageRatio", "mean"),
        StrongCandidateSessions=("SessionClassification", lambda x: (x == "STRONG_CANDIDATE").sum()),
        ReviewRequiredSessions=("SessionClassification", lambda x: (x == "REVIEW_REQUIRED").sum()),
        LowActivitySessions=("SessionClassification", lambda x: (x == "LOW_ACTIVITY").sum()),
    ).reset_index()
    recordings["OverallActivityRatio"] = (
        recordings["TotalActivitySec"] / recordings["TotalArmedDurationSec"]
    )

    concentration = recordings.sort_values(
        ["TotalActivitySec", "LogFile"], ascending=[False, True], na_position="last"
    ).reset_index(drop=True).copy()
    activity_total = concentration["TotalActivitySec"].sum(min_count=1)
    if pd.isna(activity_total) or activity_total <= 0:
        concentration["ActivitySharePct"] = np.nan
        concentration["CumulativeActivityPct"] = np.nan
        top_shares = [np.nan, np.nan, np.nan]
    else:
        concentration["ActivitySharePct"] = concentration["TotalActivitySec"] / activity_total * 100
        concentration["CumulativeActivityPct"] = concentration["ActivitySharePct"].cumsum()
        top_shares = [concentration["ActivitySharePct"].head(n).sum() for n in (1, 5, 10)]
    summary = pd.DataFrame([{
        "UniqueRecordings": data["LogFile"].nunique(),
        "ArmedSessions": len(data),
        "TotalDetectedActivitySec": activity_total,
        "Top1ActivitySharePct": top_shares[0],
        "Top5ActivitySharePct": top_shares[1],
        "Top10ActivitySharePct": top_shares[2],
        "StrongCandidateSessions": int((data["SessionClassification"] == "STRONG_CANDIDATE").sum()),
        "ReviewRequiredSessions": int((data["SessionClassification"] == "REVIEW_REQUIRED").sum()),
        "LowActivitySessions": int((data["SessionClassification"] == "LOW_ACTIVITY").sum()),
    }])
    return {
        "Baseline": baseline,
        "Classification": classification,
        "Recordings": recordings,
        "Concentration": concentration,
        "Summary": summary,
    }
