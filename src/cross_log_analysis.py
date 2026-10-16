"""Build a traceable, de-duplicated session dataset from verified batch exports.

The source of truth for each report is the batch summary's ReportDirectory,
not directory names inferred from raw .bin filenames. No flight state is inferred.
"""

from pathlib import Path

import pandas as pd


SESSION_REPORT_NAME = "flight_session_report.csv"
REQUIRED_SESSION_FIELDS = {
    "Session", "StartSec", "EndSec", "ArmedDurationSec",
    "ActivitySegments", "ActivityRatio", "SessionClassification",
}
REQUIRED_BATCH_FIELDS = {"LogFile", "Status", "ArmedSessions", "ReportDirectory"}


def consolidate_session_reports(batch_sources, master_index):
    """Return one row per reconstructed armed session from successful logs.

    Parameters
    ----------
    batch_sources : dict[str, str | pathlib.Path]
        Named authoritative batch directories, e.g. original/recovery/GPS.
    master_index : pandas.DataFrame
        Validated 102-recording index, containing LogFile, Status and
        ArmedSessions. Only entries marked SUCCESS are consolidated.

    Returns
    -------
    dict
        Sessions: combined session-level DataFrame with LogFile and source.
        Manifest: one-row-per-successful-log report provenance and counts.

    Raises
    ------
    ValueError, FileNotFoundError
        On duplicate, absent, inconsistent, or ambiguous report provenance.
    """
    if not isinstance(batch_sources, dict) or not batch_sources:
        raise ValueError("batch_sources must be a nonempty dictionary")
    if not isinstance(master_index, pd.DataFrame):
        raise TypeError("master_index must be a pandas DataFrame")
    needed = {"LogFile", "Status", "ArmedSessions"}
    if not needed.issubset(master_index.columns):
        raise ValueError(f"Master index lacks columns: {sorted(needed - set(master_index.columns))}")
    if master_index["LogFile"].isna().any() or master_index["LogFile"].duplicated().any():
        raise ValueError("Master index contains missing or duplicate LogFile values")

    expected = master_index.loc[master_index["Status"] == "SUCCESS"].copy()
    if expected.empty:
        raise ValueError("Master index has no SUCCESS recordings")
    expected_counts = pd.to_numeric(expected["ArmedSessions"], errors="coerce")
    if expected_counts.isna().any() or (expected_counts <= 0).any() or (expected_counts % 1 != 0).any():
        raise ValueError("SUCCESS entries must have positive integer ArmedSessions")
    count_by_log = dict(zip(expected["LogFile"], expected_counts.astype(int)))

    seen = set()
    session_frames = []
    manifest_rows = []
    for source_name, directory in batch_sources.items():
        batch_dir = Path(directory).expanduser().resolve()
        summary_path = batch_dir / "batch_summary.csv"
        if not summary_path.is_file():
            raise FileNotFoundError(f"Batch summary not found: {summary_path}")
        summary = pd.read_csv(summary_path)
        missing_fields = REQUIRED_BATCH_FIELDS - set(summary.columns)
        if missing_fields:
            raise ValueError(f"{source_name}: missing batch columns {sorted(missing_fields)}")
        if summary["LogFile"].isna().any() or summary["LogFile"].duplicated().any():
            raise ValueError(f"{source_name}: missing or duplicate LogFile values")

        successful = summary.loc[summary["Status"] == "SUCCESS"]
        for _, rec in successful.iterrows():
            log_name = rec["LogFile"]
            if log_name not in count_by_log:
                raise ValueError(f"Unexpected successful log in {source_name}: {log_name}")
            if log_name in seen:
                raise ValueError(f"Successful log exported by multiple selected batches: {log_name}")
            seen.add(log_name)

            if pd.isna(rec["ReportDirectory"]) or not str(rec["ReportDirectory"]).strip():
                raise ValueError(f"Missing ReportDirectory for {log_name}")
            report_dir = Path(str(rec["ReportDirectory"]))
            if not report_dir.is_absolute():
                report_dir = batch_dir / report_dir
            report_dir = report_dir.resolve()
            # Keep provenance limited to the selected batch run.
            if not report_dir.is_relative_to((batch_dir / "reports").resolve()):
                raise ValueError(f"ReportDirectory is outside batch reports for {log_name}: {report_dir}")
            report_path = report_dir / SESSION_REPORT_NAME
            if not report_path.is_file():
                raise FileNotFoundError(f"Missing session report for {log_name}: {report_path}")
            sessions = pd.read_csv(report_path)
            missing_session_fields = REQUIRED_SESSION_FIELDS - set(sessions.columns)
            if missing_session_fields:
                raise ValueError(f"{log_name}: session report lacks {sorted(missing_session_fields)}")

            master_count = count_by_log[log_name]
            batch_count = pd.to_numeric(pd.Series([rec["ArmedSessions"]]), errors="coerce").iloc[0]
            if pd.isna(batch_count) or batch_count != master_count or len(sessions) != master_count:
                raise ValueError(
                    f"Session count mismatch for {log_name}: "
                    f"master={master_count}, batch={batch_count}, report={len(sessions)}"
                )
            ids = pd.to_numeric(sessions["Session"], errors="coerce")
            if ids.isna().any() or (ids % 1 != 0).any() or ids.duplicated().any():
                raise ValueError(f"Invalid or repeated Session IDs in {log_name}")

            sessions.insert(0, "LogFile", log_name)
            sessions.insert(1, "BatchSource", str(source_name))
            sessions.insert(2, "SessionReportPath", str(report_path))
            session_frames.append(sessions)
            manifest_rows.append({
                "LogFile": log_name,
                "BatchSource": str(source_name),
                "SessionReportPath": str(report_path),
                "ArmedSessions": master_count,
            })

    missing_logs = set(count_by_log) - seen
    if missing_logs:
        raise ValueError(f"No selected authoritative report for {len(missing_logs)} successful logs: {sorted(missing_logs)}")

    all_sessions = pd.concat(session_frames, ignore_index=True)
    if all_sessions.duplicated(["LogFile", "Session"]).any():
        raise ValueError("Duplicate (LogFile, Session) keys in consolidated dataset")
    if len(all_sessions) != sum(count_by_log.values()):
        raise ValueError("Combined session count differs from master index")
    manifest = pd.DataFrame(manifest_rows)
    return {"Sessions": all_sessions, "Manifest": manifest}
