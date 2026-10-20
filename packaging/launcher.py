
"""Windows launcher for the UAV Flight Analysis System."""

import os
import sys
from pathlib import Path

# Ensure Streamlit runs in production mode inside PyInstaller.
# This must be set before importing Streamlit.
os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

from streamlit.web import cli as stcli


def main():
    """Start the local UAV Flight Analysis dashboard."""

    # Resolve bundled resources or the development project root.
    if getattr(sys, "frozen", False):
        project_root = Path(sys._MEIPASS)
    else:
        project_root = Path(__file__).resolve().parent.parent

    app_path = project_root / "dashboard" / "app.py"

    if not app_path.is_file():
        raise FileNotFoundError(
            f"Streamlit dashboard not found: {app_path}"
        )

    # Allow dashboard modules to import the project's src package.
    root_string = str(project_root)

    if root_string not in sys.path:
        sys.path.insert(0, root_string)

    # Preserve the import path for child processes.
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    pythonpath_entries = [
        entry
        for entry in existing_pythonpath.split(os.pathsep)
        if entry
    ]

    if root_string not in pythonpath_entries:
        os.environ["PYTHONPATH"] = os.pathsep.join(
            [root_string, *pythonpath_entries]
        )

    # Explicit settings required for reliable packaged startup.
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode=false",
        "--server.address=127.0.0.1",
        "--server.port=8501",
        "--server.baseUrlPath=",
        "--browser.serverAddress=127.0.0.1",
        "--browser.serverPort=8501",
        "--server.headless=false",
        "--browser.gatherUsageStats=false",
    ]

    stcli.main()


if __name__ == "__main__":
    main()
