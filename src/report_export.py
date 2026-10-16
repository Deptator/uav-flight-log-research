"""CSV export utilities for the UAV flight-log analysis pipeline.

Exports selected analysis DataFrames without changing them. Each invocation
creates a new directory so previous reports are never overwritten.
"""

from pathlib import Path
import re
import pandas as pd


REPORT_FILES = {
    "SessionReport": "flight_session_report.csv",
    "ActivitySegments": "motor_activity_segments.csv",
    "ClassifiedSegments": "flight_classifications.csv",
    "AltitudeQuality": "altitude_quality_report.csv",
}


def export_analysis_reports(results, output_root="outputs/reports"):
    """Export four verified analysis tables to a unique directory.

    Parameters
    ----------
    results : dict
        Output of ``analyze_flight_log``. Must include ``LogPath`` and the
        DataFrames named in ``REPORT_FILES``.
    output_root : str or pathlib.Path
        Parent directory under which a dedicated export folder is created.

    Returns
    -------
    dict
        Mapping from report key to the absolute Path of the exported CSV,
        plus ``OutputDirectory`` pointing to the created folder.

    Notes
    -----
    Runs are stored in ``<log_stem>``, ``<log_stem>_002`` and so on. The
    directory is created with ``exist_ok=False`` to avoid overwrites.
    """
    if not isinstance(results, dict):
        raise TypeError("results must be a dictionary from analyze_flight_log().")

    required = {"LogPath", *REPORT_FILES}
    missing = required - set(results)
    if missing:
        raise ValueError(f"Missing pipeline results: {sorted(missing)}")

    if not isinstance(results["LogPath"], (str, Path)):
        raise TypeError("results['LogPath'] must be a path string or Path.")

    for name in REPORT_FILES:
        if not isinstance(results[name], pd.DataFrame):
            raise TypeError(f"results['{name}'] must be a pandas DataFrame.")

    log_stem = Path(results["LogPath"]).stem
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", log_stem).strip("._-")
    safe_name = safe_name or "flight_log"

    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    # Reserve the folder atomically; never overwrite previously exported data.
    index = 1
    while True:
        suffix = "" if index == 1 else f"_{index:03d}"
        destination = root / f"{safe_name}{suffix}"
        try:
            destination.mkdir(exist_ok=False)
            break
        except FileExistsError:
            index += 1

    exported = {"OutputDirectory": destination}
    try:
        for key, filename in REPORT_FILES.items():
            path = destination / filename
            results[key].to_csv(path, index=False)
            exported[key] = path
    except Exception:
        # Leave any partially written directory for inspection rather than
        # silently deleting artifacts; report the error to the caller.
        raise

    return exported
