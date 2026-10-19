"""Export UAV analysis tables and optional original telemetry to Excel.

Requires openpyxl. Existing calls continue to work:
    build_excel_report(analysis, recording_name)

To include raw telemetry from a local ArduPilot BIN file:
    build_excel_report(analysis, recording_name, raw_log_path=log_path)

For an upload integration, pass decoded message DataFrames directly:
    build_excel_report(analysis, recording_name, raw_telemetry=telemetry)
"""

from datetime import date, datetime
from io import BytesIO
import math
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

REPORT_TABLES = (
    ("Session Report", "SessionReport"),
    ("Motor Activity", "ActivitySegments"),
    ("Telemetry Quality", "AltitudeQuality"),
    ("Segment Evidence", "SegmentEvidence"),
    ("Classified Segments", "ClassifiedSegments"),
    ("Session Detection", "SessionDetection"),
)
RAW_MESSAGE_TYPES = ("ARM", "RCOU", "CTUN", "GPS", "BARO", "MODE")
HEADER_FILL = PatternFill("solid", fgColor="17324D")
HEADER_FONT = Font(color="FFFFFF", bold=True)
MAX_EXCEL_ROWS = 1_048_576
MAX_EXCEL_COLUMNS = 16_384
MAX_EXCEL_TEXT = 32_767


def _excel_value(value):
    """Convert pandas scalars and guard text against Excel formula execution."""
    if value is None:
        return None
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (datetime, date, bool, int, float)):
        return value
    if not isinstance(value, str):
        value = str(value)
    # Untrusted telemetry strings must not become active spreadsheet formulas.
    if value.lstrip().startswith(("=", "+", "-", "@")):
        value = "'" + value
    return value[:MAX_EXCEL_TEXT]


def _write_table(workbook, sheet_name, frame):
    sheet = workbook.create_sheet(sheet_name)
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{sheet_name} must be a pandas DataFrame")

    if frame.index.name is not None and frame.index.name not in frame.columns:
        frame = frame.reset_index()

    if not len(frame.columns):
        sheet["A1"] = "No columns available"
        return
    if len(frame) + 1 > MAX_EXCEL_ROWS or len(frame.columns) > MAX_EXCEL_COLUMNS:
        raise ValueError(f"{sheet_name} exceeds Excel worksheet limits")

    headers = [str(col) for col in frame.columns]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 26
    sheet.freeze_panes = "A2"

    for row in frame.itertuples(index=False, name=None):
        sheet.append([_excel_value(value) for value in row])

    sheet.auto_filter.ref = sheet.dimensions
    for col_idx, header in enumerate(headers, start=1):
        width = 35 if header in {"LogFile", "SessionClassification", "ActivityStatus"} else 21
        sheet.column_dimensions[get_column_letter(col_idx)].width = width


def build_excel_report(
    analysis: dict,
    recording_name: str,
    *,
    raw_log_path=None,
    raw_telemetry=None,
) -> bytes:
    """Create an XLSX report, optionally including original telemetry samples.

    Parameters
    ----------
    analysis : dict
        Dictionary returned by the existing analyze_flight_log pipeline.
    recording_name : str
        Display name used in the workbook summary.
    raw_log_path : str or Path, optional
        Local BIN path to decode into raw worksheets. Only use when the file
        still exists; temporary upload files are deleted by the adapter.
    raw_telemetry : dict[str, pandas.DataFrame], optional
        Already parsed telemetry. Preferred for Streamlit uploads once the
        upload adapter supports returning the original decoded messages.

    Only one of raw_log_path and raw_telemetry may be provided. If neither is
    provided, the pre-existing call still exports only processed reports.
    """
    if not isinstance(analysis, dict):
        raise TypeError("analysis must be a dictionary of pipeline outputs")
    if raw_log_path is not None and raw_telemetry is not None:
        raise ValueError("Provide either raw_log_path or raw_telemetry, not both")
    if raw_log_path is not None:
        from src.log_parser import parse_flight_log
        raw_telemetry = parse_flight_log(
            raw_log_path, message_types=list(RAW_MESSAGE_TYPES)
        )
    if raw_telemetry is not None and not isinstance(raw_telemetry, dict):
        raise TypeError("raw_telemetry must be a dictionary of DataFrames")

    workbook = Workbook()
    summary = workbook.active
    summary.title = "Flight Summary"
    summary.append(["UAV Flight Analysis", "Research Report"])
    summary.append([])

    if raw_telemetry is None:
        raw_status = "Not included (no original telemetry supplied)"
    else:
        raw_status = "Included where available; missing message types labeled"

    summary_rows = [
        ("Recording", Path(recording_name).name),
        ("Armed sessions", len(analysis.get("ArmedSessions", []))),
        ("Motor activity segments", len(analysis.get("ActivitySegments", []))),
        ("Session report rows", len(analysis.get("SessionReport", []))),
        ("Interpretation", "Experimental estimates; not confirmed airborne flights"),
        ("Raw telemetry", raw_status),
    ]
    for key, value in summary_rows:
        summary.append([key, value])

    for cell in summary[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
    for row_index in range(3, 3 + len(summary_rows)):
        summary.cell(row_index, 1).font = Font(bold=True)
    summary.column_dimensions["A"].width = 30
    summary.column_dimensions["B"].width = 65
    summary.freeze_panes = "A3"

    for sheet_name, result_key in REPORT_TABLES:
        frame = analysis.get(result_key)
        if frame is not None:
            _write_table(workbook, sheet_name, frame)

    if raw_telemetry is not None:
        for message_type in RAW_MESSAGE_TYPES:
            name = f"Raw {message_type}"
            frame = raw_telemetry.get(message_type)
            if frame is None:
                missing_sheet = workbook.create_sheet(name)
                missing_sheet["A1"] = f"{message_type} messages not present in this recording"
                missing_sheet.column_dimensions["A"].width = 65
            else:
                _write_table(workbook, name, frame)

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
