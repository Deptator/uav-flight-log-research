
# UAV Flight Activity Analysis

## Overview

This project analyzes ArduPilot flight logs to identify
armed sessions, sustained motor-output activity, and
potential airborne activity.

The system uses an explainable, rule-based approach
rather than assuming that every armed interval
represents a flight.

## Analysis Pipeline

1. Parse ArduPilot BIN flight logs.
2. Reconstruct ARM-to-DISARM sessions.
3. Extract candidate motor outputs from RCOU.
4. Detect sustained high-output intervals.
5. Merge brief output interruptions.
6. Extract CTUN altitude and GPS ground-speed evidence.
7. Compare CTUN and BARO altitude measurements.
8. Classify candidate flight segments.
9. Generate session-level and segment-level reports.

## Experimental Parameters

| Parameter | Baseline Value |
|---|---|
| Candidate motor channels | C1-C4 |
| Motor-output threshold | 1350 us |
| Minimum activity duration | 3 seconds |
| Maximum merge interruption | 1 second |
| Maximum motor sample gap | 0.5 seconds |
| Altitude variation threshold | 2 metres |
| GPS speed P95 threshold | 0.5 m/s |
| CTUN-BARO disagreement warning | 2 metres |

These parameters were selected for exploratory analysis
of the current recording. They are not universal
flight-detection thresholds.

Motor-channel assignments must be verified against
the aircraft's configuration.

## Classification Labels

### STRONG_CANDIDATE

A sustained motor-activity segment with both altitude
and GPS evidence meeting the baseline thresholds,
without a detected altitude-quality warning.

This is not a confirmed flight.

### REVIEW_REQUIRED

A segment with insufficient, contradictory, or
quality-flagged supporting evidence.

### LOW_ACTIVITY

An armed session containing no qualifying sustained
high-output segment under the selected parameters.

This does not prove that the aircraft stayed grounded.

## Current Research Results

The selected recording contains:

- 9 complete armed sessions
- 8 sustained motor-activity segments
- 7 strong candidate segments
- 1 segment requiring review
- 2 armed sessions with no qualifying motor activity

Session 6 contains two separate motor-activity segments
within one armed interval.

Session 9 contains a significant late CTUN-BARO
altitude disagreement and requires further investigation.

These results describe one analyzed recording and do
not establish general flight-detection accuracy.

## Source Modules

- `src/log_parser.py` - Flight-log parsing
- `src/flight_detection.py` - Motor-activity segmentation
- `src/telemetry_quality.py` - Altitude-source comparison
- `src/flight_classification.py` - Candidate classification
  and session reporting

## Generated Reports

The analysis currently exports:

- `flight_session_report.csv`
- `motor_activity_segments.csv`
- `flight_classifications.csv`
- `altitude_quality_report.csv`

These files are stored in `data/processed/`.

## Known Limitations

- Candidate motor channels have not been independently
  verified against aircraft output configuration.
- Elevated motor output does not independently prove
  airborne flight.
- GPS ground speed cannot reliably distinguish
  stationary hovering from ground activity.
- Altitude variation can include estimator errors.
- CTUN and BARO are not fully independent measurements.
- Thresholds are experimental and aircraft-dependent.
- The classifier has not been validated against
  independently confirmed takeoff and landing events.
- The end-to-end processing pipeline is not yet fully
  consolidated into reusable source code.

## Future Improvements

- Aircraft motor-channel configuration validation
- Automated takeoff and landing event investigation
- Additional estimator and sensor-quality checks
- Multi-log evaluation with labeled flight events
- Configurable detection parameters
- Reusable end-to-end processing pipeline
- Offline interactive flight-analysis dashboard
