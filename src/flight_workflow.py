"""
UAV Flight Analysis Workflow.

Runs the analysis pipeline and exports its CSV reports.
"""

from pathlib import Path

from src.analysis_pipeline import analyze_flight_log
from src.report_export import export_analysis_reports


def process_flight_log(log_path, output_root=None, **analysis_options):
    """
    Analyze an ArduPilot BIN log and export CSV reports.

    Returns
    -------
    dict
        Analysis results and exported report paths.
    """
    project_root = Path(__file__).resolve().parent.parent

    if output_root is None:
        output_root = project_root / "outputs" / "reports"

    results = analyze_flight_log(
        log_path,
        **analysis_options
    )

    exported = export_analysis_reports(
        results,
        output_root=output_root
    )

    return {
        "Analysis": results,
        "Exports": exported
    }