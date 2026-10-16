"""Read-only telemetry inventory for ArduPilot BIN flight logs.

This module reports observed message availability and timestamp coverage.
It does not infer arming, airborne flight, or motor activity from missing events.
"""

from pathlib import Path
import numpy as np
import pandas as pd

from src.log_parser import parse_flight_log

MESSAGE_TYPES = ("ARM", "RCOU", "CTUN", "GPS", "BARO")
CORE_TYPES = ("ARM", "RCOU", "CTUN", "BARO")


def _timing(df):
    """Return observed timestamp details, or missing values when unavailable."""
    empty = {
        "ValidTimestampSamples": 0,
        "StartSec": np.nan,
        "EndSec": np.nan,
        "SpanSec": np.nan,
        "LargestGapSec": np.nan,
    }
    if df is None or "TimeUS" not in df.columns or df.empty:
        return empty
    sec = pd.to_numeric(df["TimeUS"], errors="coerce") / 1_000_000
    sec = np.sort(sec[np.isfinite(sec)].unique())
    if len(sec) == 0:
        return empty
    differences = np.diff(sec)
    return {
        "ValidTimestampSamples": int(len(sec)),
        "StartSec": float(sec[0]),
        "EndSec": float(sec[-1]),
        "SpanSec": float(sec[-1] - sec[0]),
        "LargestGapSec": float(differences.max()) if len(differences) else np.nan,
    }


def _complete_arm_intervals(arm_df):
    """Count only observed, complete ARM(1) then DISARM(0) pairs."""
    if arm_df is None or not {"TimeUS", "ArmState"}.issubset(arm_df.columns):
        return 0
    events = arm_df[["TimeUS", "ArmState"]].copy()
    events["TimeUS"] = pd.to_numeric(events["TimeUS"], errors="coerce")
    events["ArmState"] = pd.to_numeric(events["ArmState"], errors="coerce")
    events = events.dropna().sort_values("TimeUS")
    armed_at = None
    count = 0
    for time_us, state in events.itertuples(index=False, name=None):
        if state == 1 and armed_at is None:
            armed_at = time_us
        elif state == 0 and armed_at is not None and time_us >= armed_at:
            count += 1
            armed_at = None
    return count


def inspect_telemetry(log_path):
    """Inventory one BIN log without performing session or flight classification.

    Returns a dict with Summary (one-row DataFrame) and Messages
    (one row per expected message type). Raises on file/parser errors.
    """
    path = Path(log_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Flight log not found: {path}")
    if path.suffix.lower() != ".bin":
        raise ValueError(f"Expected .bin log: {path}")

    parsed = parse_flight_log(path, message_types=list(MESSAGE_TYPES))
    parsed = parsed or {}
    message_rows = []
    for name in MESSAGE_TYPES:
        frame = parsed.get(name)
        count = int(len(frame)) if frame is not None else 0
        time_info = _timing(frame)
        message_rows.append({
            "MessageType": name,
            "Available": bool(count),
            "Records": count,
            **time_info,
        })
    messages = pd.DataFrame(message_rows)
    counts = dict(zip(messages["MessageType"], messages["Records"]))
    rcou = messages.loc[messages["MessageType"] == "RCOU"].iloc[0]
    missing = [name for name in MESSAGE_TYPES if counts[name] == 0]
    missing_core = [name for name in CORE_TYPES if counts[name] == 0]
    complete = _complete_arm_intervals(parsed.get("ARM"))
    summary = pd.DataFrame([{
        "LogFile": path.name,
        "LogPath": str(path),
        "FileSizeBytes": path.stat().st_size,
        "ARMRecords": counts["ARM"],
        "RCOURecords": counts["RCOU"],
        "CTUNRecords": counts["CTUN"],
        "GPSRecords": counts["GPS"],
        "BARORecords": counts["BARO"],
        "MissingMessages": ",".join(missing),
        "MissingCoreMessages": ",".join(missing_core),
        "CompleteArmedIntervals": complete,
        "ArmedSessionsReconstructable": bool(complete),
        "RCOUValidTimestampSamples": int(rcou["ValidTimestampSamples"]),
        "RCOUStartSec": rcou["StartSec"],
        "RCOUEndSec": rcou["EndSec"],
        "RCOUSpanSec": rcou["SpanSec"],
        "RCOULargestGapSec": rcou["LargestGapSec"],
        "DiagnosticStatus": (
            "MISSING_ARM" if counts["ARM"] == 0
            else "NO_COMPLETE_SESSIONS" if complete == 0
            else "COMPLETE_ARM_INTERVALS_PRESENT"
        ),
    }])
    return {"Summary": summary, "Messages": messages}


def inspect_telemetry_batch(log_paths, output_csv=None):
    """Inventory multiple logs; retain one row per input even on errors.

    If output_csv is provided, create the parent folder and save the CSV.
    """
    rows = []
    for path in log_paths:
        try:
            row = inspect_telemetry(path)["Summary"].iloc[0].to_dict()
            row["ErrorType"] = None
            row["ErrorMessage"] = None
        except Exception as exc:
            row = {
                "LogFile": Path(path).name,
                "LogPath": str(path),
                "DiagnosticStatus": "FAILED",
                "ErrorType": type(exc).__name__,
                "ErrorMessage": str(exc),
            }
        rows.append(row)
    result = pd.DataFrame(rows)
    if output_csv is not None:
        destination = Path(output_csv)
        destination.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(destination, index=False)
    return result
