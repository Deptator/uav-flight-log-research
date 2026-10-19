"""Safely adapt an uploaded ArduPilot BIN log to the existing analysis pipeline.

This module performs analysis only; it does not write CSV reports or modify
previously processed dataset outputs.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from src.analysis_pipeline import analyze_flight_log


def analyze_uploaded_log(filename: str, content: bytes) -> dict:
    """Analyze uploaded BIN bytes using the existing flight-log pipeline.

    Parameters
    ----------
    filename:
        Original filename, used only for validation and display.
    content:
        Bytes of the uploaded ArduPilot DataFlash BIN recording.

    Returns
    -------
    dict
        Original filename and the result from ``analyze_flight_log``.

    Notes
    -----
    The uploaded file is stored temporarily while it is decoded and is
    automatically removed afterward. No existing recordings are overwritten.
    """
    original_name = Path(filename).name
    if Path(original_name).suffix.lower() != ".bin":
        raise ValueError("Please upload an ArduPilot .bin flight log.")
    if not isinstance(content, bytes) or not content:
        raise ValueError("The uploaded flight log is empty or invalid.")

    with TemporaryDirectory(prefix="uav_log_upload_") as directory:
        temporary_log = Path(directory) / "uploaded.bin"
        temporary_log.write_bytes(content)
        analysis = analyze_flight_log(temporary_log)

    # The temporary file has been deleted. Do not return its obsolete path.
    analysis.pop("LogPath", None)
    return {"Filename": original_name, "Analysis": analysis}
