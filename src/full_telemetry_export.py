"""Export every available ArduPilot DataFlash message type to one Excel workbook.

This is separate from src.excel_export.build_excel_report, which remains unchanged.
Uses a write-only workbook to limit memory consumption for large recordings.

Usage:
    from src.full_telemetry_export import build_full_telemetry_excel
    data = build_full_telemetry_excel('data/raw/example.bin')

A pre-parsed dictionary can also be supplied with raw_telemetry=... instead of
parsing the log again. No messages are intentionally discarded.
"""

from datetime import datetime, timezone
from io import BytesIO
import re
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment
from openpyxl.utils.exceptions import IllegalCharacterError

from src.excel_export import (
    HEADER_FILL,
    HEADER_FONT,
    MAX_EXCEL_COLUMNS,
    MAX_EXCEL_ROWS,
    _excel_value,
)

_INVALID_SHEET_CHARS = re.compile(r"[\\/*?:\[\]]")
_DATA_ROWS_PER_SHEET = MAX_EXCEL_ROWS - 1  # Header consumes row 1.


def _unique_sheet_name(preferred: str, used: set[str]) -> str:
    """Make a legal, unique Excel worksheet name (case-insensitive)."""
    base = _INVALID_SHEET_CHARS.sub("_", str(preferred)).strip("'") or "Message"
    base = base[:31]
    name = base
    suffix_num = 2
    while name.casefold() in used:
        suffix = f"_{suffix_num}"
        name = base[:31 - len(suffix)] + suffix
        suffix_num += 1
    used.add(name.casefold())
    return name


def _header(sheet, column_names):
    cells = []
    for column in column_names:
        cell = WriteOnlyCell(sheet, value=str(column))
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center")
        cells.append(cell)
    sheet.append(cells)


def build_full_telemetry_excel(log_path=None, *, raw_telemetry=None) -> bytes:
    """Return XLSX bytes including an inventory and every available message type.

    Parameters
    ----------
    log_path : str or pathlib.Path, optional
        Existing ArduPilot DataFlash .bin log; parsed exactly once.
    raw_telemetry : dict[str, pandas.DataFrame], optional
        Already parsed messages, for integration without redundant decoding.

    Exactly one input must be provided. A message with more than 1,048,575
    records is split across multiple worksheets rather than truncated.
    """
    if (log_path is None) == (raw_telemetry is None):
        raise ValueError("Provide exactly one of log_path or raw_telemetry")

    if log_path is not None:
        path = Path(log_path)
        if not path.is_file() or path.suffix.lower() != ".bin":
            raise ValueError("Provide an existing ArduPilot .bin log path")
        from src.log_parser import parse_flight_log
        raw_telemetry = parse_flight_log(path)
        recording = path.name
    else:
        recording = "Pre-parsed telemetry"

    if not isinstance(raw_telemetry, dict):
        raise TypeError("raw_telemetry must be a dictionary of pandas DataFrames")
    if not raw_telemetry:
        raise ValueError("No telemetry messages were found to export")

    # Validate first, before allocating a potentially large workbook.
    for msg_type, frame in raw_telemetry.items():
        if not isinstance(frame, pd.DataFrame):
            raise TypeError(f"{msg_type}: expected a pandas DataFrame")
        additional = int(frame.index.name is not None and frame.index.name not in frame.columns)
        if len(frame.columns) + additional > MAX_EXCEL_COLUMNS:
            raise ValueError(f"{msg_type}: too many columns for Excel")

    wb = Workbook(write_only=True)
    used = set()
    summary = wb.create_sheet(_unique_sheet_name("Message Inventory", used))
    summary.freeze_panes = "A2"
    _header(summary, ["Message Type", "Records", "Fields", "Worksheet(s)"])

    total_records = 0
    total_types = 0
    inventory_rows = []

    for msg_type, frame in sorted(raw_telemetry.items(), key=lambda pair: str(pair[0])):
        if frame.index.name is not None and frame.index.name not in frame.columns:
            frame = frame.reset_index()

        headers = [str(x) for x in frame.columns]
        if not headers:  # A type with no recorded fields must still be visible.
            headers = ["Note"]
            frame = pd.DataFrame({"Note": ["Message exists but contains no fields"]})

        rows = len(frame)
        parts = max(1, (rows + _DATA_ROWS_PER_SHEET - 1) // _DATA_ROWS_PER_SHEET)
        names = []

        for part in range(parts):
            preferred = f"Raw {msg_type}" if parts == 1 else f"Raw {msg_type} {part + 1}"
            name = _unique_sheet_name(preferred, used)
            names.append(name)
            sheet = wb.create_sheet(name)
            sheet.freeze_panes = "A2"
            _header(sheet, headers)

            start = part * _DATA_ROWS_PER_SHEET
            stop = min(rows, start + _DATA_ROWS_PER_SHEET)
            for row in frame.iloc[start:stop].itertuples(index=False, name=None):
                try:
                    sheet.append([_excel_value(value) for value in row])
                except IllegalCharacterError as exc:
                    raise ValueError(
                        f"{msg_type}: telemetry contains illegal Excel control characters"
                    ) from exc

        inventory_rows.append((str(msg_type), rows, len(headers), ", ".join(names)))
        total_types += 1
        total_records += rows

    for row in inventory_rows:
        summary.append([_excel_value(cell) for cell in row])

    # Keep summary explicit and separate from telemetry rows; avoid adding a
    # count row that might be mistaken for another message type.
    notes = wb.create_sheet(_unique_sheet_name("Export Notes", used))
    notes.append(["Recording", _excel_value(recording)])
    notes.append(["Message types exported", total_types])
    notes.append(["Total message records", total_records])
    notes.append(["Timestamp meaning", "TimeUS values are preserved as provided by the flight log"])
    notes.append(["Data integrity", "Missing data stays missing; message types are not synchronized row-by-row"])
    notes.append(["Interpretation", "Telemetry values are recorded observations, not proof of airborne flight"])

    output = BytesIO()
    wb.save(output)
    return output.getvalue()
