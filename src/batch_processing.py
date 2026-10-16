"""Fault-isolated batch processing for ArduPilot BIN flight logs.

Each run gets a unique output directory and a CSV manifest.
Statuses distinguish completed logs with sessions (SUCCESS), completed logs
without complete ARM/DISARM sessions (NO_COMPLETE_SESSIONS), and failures
(FAILED). The module reuses
src.flight_workflow.process_flight_log instead of reimplementing analysis.
Experimental candidate labels are not confirmations of airborne flight.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.flight_workflow import process_flight_log


BATCH_COLUMNS = [
    "LogFile", "LogPath", "FileSizeBytes", "Status", "ArmedSessions",
    "ActivitySegments", "StrongCandidateSessions", "LowActivitySessions",
    "ReviewRequiredSessions", "ReportDirectory", "ErrorType", "ErrorMessage",
]


def discover_flight_logs(raw_dir):
    """Return BIN files in a single directory, ordered by filename."""
    directory = Path(raw_dir).expanduser().resolve()
    if not directory.is_dir():
        raise NotADirectoryError(f"Raw-log directory not found: {directory}")
    return sorted(
        (p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".bin"),
        key=lambda p: (p.name.casefold(), p.name),
    )


def _make_unique_batch_directory(output_root):
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    stem = "batch_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for index in range(1, 10000):
        name = stem if index == 1 else f"{stem}_{index:03d}"
        destination = root / name
        try:
            destination.mkdir(exist_ok=False)
            return destination
        except FileExistsError:
            continue
    raise RuntimeError("Could not allocate a unique batch output directory")


def process_flight_logs(
    raw_dir,
    *,
    log_paths=None,
    max_logs=None,
    output_root=None,
    analysis_options=None,
):
    """Analyze several BIN files, isolating failures and saving a batch summary.

    Parameters
    ----------
    raw_dir : path
        Folder used for discovery when log_paths is None.
    log_paths : sequence of paths or None
        Explicit list to process, in given order. Relative paths are resolved
        relative to raw_dir. No filename-derived date assumptions are made.
    max_logs : int or None
        Optional positive limit for controlled pilot runs.
    output_root : path or None
        Batch runs go in <project>/outputs/batches by default.
    analysis_options : mapping or None
        Keyword arguments forwarded to analyze_flight_log via workflow.

    Returns
    -------
    dict
        BatchDirectory (Path), SummaryPath (Path), Summary (DataFrame).
    """
    raw_path = Path(raw_dir).expanduser().resolve()
    if not raw_path.is_dir():
        raise NotADirectoryError(f"Raw-log directory not found: {raw_path}")

    if max_logs is not None and (isinstance(max_logs, bool) or not isinstance(max_logs, int) or max_logs < 1):
        raise ValueError("max_logs must be a positive integer or None")

    if log_paths is None:
        logs = discover_flight_logs(raw_path)
    else:
        logs = []
        for value in log_paths:
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = raw_path / path
            logs.append(path.resolve())
        if len(set(logs)) != len(logs):
            raise ValueError("log_paths contains duplicate files")
        if any(p.suffix.lower() != ".bin" for p in logs):
            raise ValueError("log_paths must contain .bin filenames only")

    if max_logs is not None:
        logs = logs[:max_logs]
    if not logs:
        raise ValueError("No BIN logs selected for batch processing")

    if output_root is None:
        output_root = Path(__file__).resolve().parent.parent / "outputs" / "batches"
    run_dir = _make_unique_batch_directory(output_root)
    reports_dir = run_dir / "reports"
    options = dict(analysis_options or {})
    rows = []

    for index, log_path in enumerate(logs, start=1):
        row = dict.fromkeys(BATCH_COLUMNS)
        row.update({
            "LogFile": log_path.name,
            "LogPath": str(log_path),
            "FileSizeBytes": log_path.stat().st_size if log_path.is_file() else pd.NA,
            "Status": "FAILED",
        })
        try:
            outcome = process_flight_log(
                log_path, output_root=reports_dir, **options
            )
            analysis = outcome["Analysis"]
            report = analysis["SessionReport"]
            counts = report["SessionClassification"].value_counts()
            row.update({
                "Status": "SUCCESS" if len(report) > 0 else "NO_COMPLETE_SESSIONS",
                "ArmedSessions": len(report),
                "ActivitySegments": len(analysis["ActivitySegments"]),
                "StrongCandidateSessions": int(counts.get("STRONG_CANDIDATE", 0)),
                "LowActivitySessions": int(counts.get("LOW_ACTIVITY", 0)),
                "ReviewRequiredSessions": int(counts.get("REVIEW_REQUIRED", 0)),
                "ReportDirectory": str(outcome["Exports"]["OutputDirectory"]),
            })
        except Exception as exc:
            row["ErrorType"] = type(exc).__name__
            row["ErrorMessage"] = str(exc)
        rows.append(row)
        print(f"[{index}/{len(logs)}] {row['Status']}: {log_path.name}")

    summary = pd.DataFrame(rows, columns=BATCH_COLUMNS)
    summary_path = run_dir / "batch_summary.csv"
    summary.to_csv(summary_path, index=False)
    return {
        "BatchDirectory": run_dir,
        "SummaryPath": summary_path,
        "Summary": summary,
    }
