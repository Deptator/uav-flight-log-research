# 🚁 UAV Flight Log Research & Analysis System

A Python-based research application for analyzing experimental UAV flight-controller logs recorded using the **RadioLink CrossFlight** flight controller.

The project transforms raw ArduPilot DataFlash (`.bin`) recordings into structured telemetry, interactive visualizations, session-level statistics, exploratory anomaly reports, and downloadable Excel datasets.

Developed as part of an experimental UAV telemetry research initiative.

## Project Objectives

- Decode and interpret flight-controller telemetry.
- Analyze GPS, IMU, vibration, attitude, altitude, and motor outputs.
- Automate repetitive analysis of UAV flight recordings.
- Reconstruct armed sessions and detect motor-activity intervals.
- Explore unsupervised machine-learning techniques for anomaly detection.
- Provide an offline-capable dashboard for researchers.
- Export processed results and original telemetry for further analysis.

## Key Features

### 1. Automated Flight Log Processing

- Parses ArduPilot DataFlash `.bin` recordings using PyMAVLink.
- Extracts available telemetry message types and their recorded fields.
- Processes multiple recordings through a reusable analysis pipeline.
- Handles recordings with missing or incomplete required telemetry.

### 2. Flight Session Analysis

- Reconstructs armed sessions using available flight-controller records.
- Identifies motor-activity segments.
- Generates session-level statistics and experimental classifications.
- Evaluates telemetry availability and quality.

### 3. Interactive Telemetry Visualization

Visualizations include:

- CTUN altitude measurements
- GPS ground speed
- RCOU motor PWM outputs
- Synchronized telemetry comparison
- User-selected time-window inspection

### 4. Exploratory Anomaly Detection

- Uses an Isolation Forest-based experimental anomaly-detection workflow.
- Highlights unusual patterns in derived flight-session features.
- Provides an interactive anomaly explorer for further investigation.

**Important:** Anomaly flags are exploratory and do not independently establish actual UAV faults.

### 5. Streamlit Research Dashboard

The application includes seven sections:

1. Overview
2. Recording Inventory
3. Session Statistics
4. Session Explorer
5. Anomaly Explorer
6. Telemetry Diagnostics
7. Upload & Analyze

Researchers can upload new supported `.bin` recordings without modifying the source code.

### 6. CSV and Excel Exports

The application supports:

- Session Report (CSV)
- Flight Analysis Report (Excel)
- Selected Time-Window Telemetry (Excel)
- Complete Raw Telemetry (Excel)

The complete raw telemetry exporter creates separate worksheets for all available message types in a recording.

## Dataset and Experimental Results

The initial research dataset contains **102 experimental UAV recordings**.

| Processing outcome | Recordings |
|---|---:|
| Total recordings | 102 |
| Successfully analyzed | 50 |
| No complete armed sessions | 25 |
| Missing ARM telemetry | 27 |

Across successfully analyzed recordings, the pipeline identified:

- 158 reconstructed armed sessions
- 86 motor-activity segments

The largest tested recording contained 55 telemetry message types and 379,338 recorded messages.

These figures describe the initial research dataset and are not general performance benchmarks.

## Technology Stack

| Category | Technologies |
|---|---|
| Programming | Python 3.11 |
| Flight-log parsing | PyMAVLink |
| Data processing | Pandas, NumPy |
| Machine learning | Scikit-learn |
| Visualization | Streamlit, Plotly, Matplotlib |
| Spreadsheet export | OpenPyXL |
| Development | JupyterLab, VS Code |
| Windows packaging | PyInstaller |
| Version control | Git, GitHub |

## Project Structure

```text
Drone-research/
├── dashboard/
│   ├── app.py
│   └── components/
├── src/
│   ├── log_parser.py
│   ├── analysis_pipeline.py
│   ├── anomaly_detection.py
│   ├── excel_export.py
│   ├── full_telemetry_export.py
│   └── ...
├── notebooks/
├── docs/
├── packaging/
│   ├── launcher.py
│   └── uav_analyzer.spec
├── data/
│   └── raw/
├── outputs/
├── requirements.txt
├── .gitignore
└── README.md
```

Some directories contain local research data or generated outputs and are excluded from version control.

## Running the Application

### Development Environment

From the project root, using a compatible Python environment with the required dependencies installed:

```powershell
python -m streamlit run dashboard/app.py
```

The dashboard normally opens at:

`http://localhost:8501`

Historical dashboard sections require their previously generated CSV reports under `outputs/`.

### Packaged Windows Application

A Windows application has been prepared using PyInstaller.

1. Extract the supplied release ZIP.
2. Open the `UAV-Flight-Analyzer` folder.
3. Double-click `UAV-Flight-Analyzer.exe`.
4. Open `http://127.0.0.1:8501` if the browser does not open automatically.
5. Keep the application's console window open while using the dashboard.

The complete packaged folder must remain intact, including `_internal`.

The application has been tested on the development Windows machine and from a separate directory. Independent testing on another Windows computer remains pending.

## Research Limitations

- Reconstructed armed sessions are not independently verified airborne flights.
- Detected motor activity does not necessarily indicate takeoff.
- Machine-learning anomaly flags are not validated fault diagnoses.
- Session reconstruction depends on the telemetry recorded by the flight controller.
- Some recordings lack ARM messages or other required data.
- Processing and export times depend on recording size and system resources.
- The application is intended for research and post-flight analysis, not real-time flight control.

## Data Availability

Experimental UAV flight logs are stored locally and are **not included in this repository**.

Generated datasets, exported reports, and packaged application binaries are excluded from Git tracking.

Access to original recordings and research datasets is subject to the permissions of the collaborating research team.

## Project Status

**Development and local Windows packaging completed.**

Completed work includes:

- Flight-log exploration and decoding
- Automated processing pipeline
- Session statistics and telemetry diagnostics
- Exploratory anomaly detection
- Interactive Streamlit dashboard
- Excel and CSV export capabilities
- PyInstaller-based Windows packaging
- Local executable and export testing

**Pending:** Independent Windows-machine validation and final research handover.

## Future Research Directions

- Improve anomaly detection using independently labeled flight events and faults.
- Investigate supervised fault classification when validated labels are available.
- Compare telemetry patterns across UAV experiments.
- Expand telemetry quality assessment and diagnostic reporting.
- Explore predictive health monitoring after sufficient validation.

---

*UAV Flight Log Research & Analysis System — Experimental research software.*
