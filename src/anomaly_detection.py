"""Reproducible exploratory session-level anomaly screening for UAV logs.

Flags describe statistical unusualness, NOT confirmed flight faults.
The model is fitted and scored on the same dataset; no unseen-data validation.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

REQUIRED_COLUMNS = (
    "LogFile", "Session", "ArmedDurationSec", "ActivityRatio",
)


def analyze_session_anomalies(
    sessions: pd.DataFrame,
    *,
    contamination: float = 0.05,
    random_state: int = 42,
    n_estimators: int = 200,
    consensus_seeds: Iterable[int] = (7, 21, 42, 99),
) -> dict[str, pd.DataFrame]:
    """Fit Isolation Forest, compare duration IQR and estimate seed consensus.

    Returns 'Sessions', 'Summary', 'ConsensusSummary', and 'SeedStability'.
    Original rows, identifiers, and classifications (if present) are preserved.
    """
    if not isinstance(sessions, pd.DataFrame):
        raise TypeError("sessions must be a pandas DataFrame")
    missing = sorted(set(REQUIRED_COLUMNS) - set(sessions.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    if sessions.empty:
        raise ValueError("No sessions supplied")
    if sessions.duplicated(["LogFile", "Session"]).any():
        raise ValueError("Duplicate (LogFile, Session) identities")
    if not 0 < contamination < 0.5:
        raise ValueError("contamination must be between 0 and 0.5")
    seeds = tuple(int(x) for x in consensus_seeds)
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("consensus_seeds must be nonempty and unique")

    result = sessions.copy().reset_index(drop=True)
    cols = ["ArmedDurationSec", "ActivityRatio"]
    numeric = result[cols].apply(pd.to_numeric, errors="coerce")
    raw = numeric.to_numpy(dtype=float)
    if not np.isfinite(raw).all():
        raise ValueError("Missing/nonfinite duration or activity ratio")
    if not (numeric["ArmedDurationSec"] > 0).all():
        raise ValueError("Armed durations must be positive")
    if not numeric["ActivityRatio"].between(0, 1).all():
        raise ValueError("Activity ratios must be in [0, 1]")
    result[cols] = numeric

    result["LogArmedDuration"] = np.log1p(result["ArmedDurationSec"])
    features = ["LogArmedDuration", "ActivityRatio"]
    matrix = RobustScaler().fit_transform(result[features])

    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    flags = model.fit_predict(matrix) == -1
    result["AnomalyScore"] = -model.score_samples(matrix)
    result["AnomalyFlag"] = flags

    q1, q3 = result["ArmedDurationSec"].quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    iqr_flag = ~result["ArmedDurationSec"].between(lower, upper, inclusive="both")
    result["IQRDurationFlag"] = iqr_flag
    result["DetectionAgreement"] = np.select(
        [flags & iqr_flag, flags & ~iqr_flag, ~flags & iqr_flag],
        ["BOTH", "ISOLATION_FOREST_ONLY", "IQR_ONLY"],
        default="NEITHER",
    )

    seed_rows = []
    all_flags = []
    for seed in seeds:
        trial = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=seed,
            n_jobs=-1,
        )
        trial_flags = trial.fit_predict(matrix) == -1
        all_flags.append(trial_flags)
        overlap = int(np.count_nonzero(flags & trial_flags))
        union = int(np.count_nonzero(flags | trial_flags))
        seed_rows.append({
            "Contamination": contamination,
            "RandomSeed": seed,
            "FlaggedSessions": int(trial_flags.sum()),
            "OverlapWithBaseline": overlap,
            "JaccardSimilarity": overlap / union if union else 1.0,
        })

    flag_count = np.column_stack(all_flags).sum(axis=1)
    result["FlagCount"] = flag_count.astype(int)
    result["FlagFrequency"] = flag_count / len(seeds)
    result["ConsensusStatus"] = np.select(
        [flag_count == len(seeds), flag_count > 0],
        ["CONSISTENTLY_FLAGGED", "VARIABLE_FLAG"],
        default="NOT_FLAGGED",
    )

    summary = pd.DataFrame([{
        "Sessions": len(result),
        "UniqueRecordings": result["LogFile"].nunique(),
        "IsolationForestFlags": int(flags.sum()),
        "IQRDurationFlags": int(iqr_flag.sum()),
        "BothMethods": int((flags & iqr_flag).sum()),
        "IsolationForestOnly": int((flags & ~iqr_flag).sum()),
        "IQROnly": int((~flags & iqr_flag).sum()),
        "IQRLowerThresholdSec": float(lower),
        "IQRUpperThresholdSec": float(upper),
        "Contamination": contamination,
        "RandomState": random_state,
        "Estimators": n_estimators,
    }])
    statuses = ["CONSISTENTLY_FLAGGED", "VARIABLE_FLAG", "NOT_FLAGGED"]
    counts = result["ConsensusStatus"].value_counts()
    consensus_summary = pd.DataFrame({
        "ConsensusStatus": statuses,
        "Sessions": [int(counts.get(status, 0)) for status in statuses],
    })
    return {
        "Sessions": result,
        "Summary": summary,
        "ConsensusSummary": consensus_summary,
        "SeedStability": pd.DataFrame(seed_rows),
    }
