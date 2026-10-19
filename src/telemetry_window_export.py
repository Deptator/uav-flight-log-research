"""Export a selected, synchronized UAV telemetry time window as XLSX bytes.

Input is the dictionary returned by prepare_comparison_data(). No resampling,
interpolation, or modification of the source recording is performed.
"""

from io import BytesIO
import math

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

_HEADER_FILL = PatternFill(fill_type="solid", fgColor="17324D")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_TYPES = (("CTUN", "CTUN"), ("GPS", "GPS Valid"), ("RCOU", "RCOU"))


def _excel_cell(value):
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
        except (ValueError, TypeError):
            pass
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, bytes)):
        value = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
        if value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
    elif not isinstance(value, (int, float, bool)):
        value = str(value)
    return value


def _append_table(workbook, title, frame):
    sheet = workbook.create_sheet(title)
    if len(frame) + 1 > 1_048_576 or len(frame.columns) > 16_384:
        raise ValueError(f"{title} exceeds Excel's worksheet dimensions")
    if not len(frame.columns):
        sheet.append(["No fields available"])
        return
    sheet.append([str(name) for name in frame.columns])
    for cell in sheet[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
    sheet.freeze_panes = "A2"
    sheet.row_dimensions[1].height = 24
    for row in frame.itertuples(index=False, name=None):
        sheet.append([_excel_cell(v) for v in row])
    sheet.auto_filter.ref = sheet.dimensions
    for index, header in enumerate(frame.columns, 1):
        sheet.column_dimensions[get_column_letter(index)].width = min(max(len(str(header)) + 4, 16), 30)


def build_telemetry_window_excel(telemetry: dict, start_sec: float, end_sec: float) -> bytes:
    """Export CTUN, valid GPS and RCOU rows within an inclusive elapsed-time interval.

    All dataframes must come from prepare_comparison_data() and therefore use
    the same ElapsedSec reference. GPS rows follow the comparison plot's filters:
    Status >= 3, Spd >= 0 and valid numeric speed. No missing values are filled.
    """
    if not isinstance(telemetry, dict):
        raise TypeError("telemetry must be a dictionary of pandas DataFrames")
    start, end = float(start_sec), float(end_sec)
    if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end):
        raise ValueError("Expected a finite time window with 0 <= start < end")

    slices = {}
    for message_type, sheet_name in _TYPES:
        frame = telemetry.get(message_type)
        if frame is None:
            continue
        if not isinstance(frame, pd.DataFrame) or "ElapsedSec" not in frame.columns:
            raise ValueError(f"{message_type} must contain an ElapsedSec column")
        times = pd.to_numeric(frame["ElapsedSec"], errors="coerce")
        subset = frame.loc[times.between(start, end)].copy()
        if message_type == "GPS":
            if not {"Status", "Spd"}.issubset(subset.columns):
                subset = subset.iloc[0:0]
            else:
                status = pd.to_numeric(subset["Status"], errors="coerce")
                speed = pd.to_numeric(subset["Spd"], errors="coerce")
                subset = subset.loc[(status >= 3) & (speed >= 0) & speed.notna()]
        # Preserve original TimeUS and every original telemetry field; append
        # TimeSec / ElapsedSec, which are created by prepare_comparison_data().
        slices[sheet_name] = subset.reset_index(drop=True)

    workbook = Workbook()
    summary = workbook.active
    summary.title = "Window Summary"
    rows = [
        ("UAV Telemetry Window Export", ""),
        ("Start elapsed time (s)", start),
        ("End elapsed time (s)", end),
        ("Window duration (s)", end - start),
        ("Time reference", "Shared origin across CTUN, GPS and RCOU"),
        ("GPS quality", "Status >= 3 and nonnegative numeric speed"),
        ("Sampling", "Original samples only; no interpolation"),
        ("CTUN rows", len(slices.get("CTUN", []))),
        ("GPS Valid rows", len(slices.get("GPS Valid", []))),
        ("RCOU rows", len(slices.get("RCOU", []))),
        ("Interpretation", "Research measurements; not confirmed flight"),
    ]
    for row in rows:
        summary.append(row)
    for cell in summary[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
    for row in range(2, len(rows) + 1):
        summary.cell(row, 1).font = Font(bold=True)
    summary.column_dimensions["A"].width = 30
    summary.column_dimensions["B"].width = 60
    summary.freeze_panes = "A2"

    for _, sheet_name in _TYPES:
        if sheet_name in slices:
            _append_table(workbook, sheet_name, slices[sheet_name])

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
