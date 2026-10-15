
from pathlib import Path

import pandas as pd
from pymavlink import mavutil


def parse_flight_log(log_path, message_types=None):
    """
    Parse an ArduPilot DataFlash BIN log in one pass.

    Parameters
    ----------
    log_path : str or Path
        Path to the flight log.

    message_types : list or None
        Message types to extract.
        If None, extract all message types.

    Returns
    -------
    dict
        Dictionary mapping message types
        to Pandas DataFrames.
    """

    log_path = Path(log_path)

    if not log_path.is_file():
        raise FileNotFoundError(
            f"Flight log not found: {log_path}"
        )

    selected_types = (
        set(message_types)
        if message_types is not None
        else None
    )

    records = {}

    log = mavutil.mavlink_connection(str(log_path))

    while True:
        msg = log.recv_match()

        if msg is None:
            break

        msg_type = msg.get_type()

        if (
            selected_types is not None
            and msg_type not in selected_types
        ):
            continue

        records.setdefault(msg_type, []).append(
            msg.to_dict()
        )

    datasets = {}

    for msg_type, rows in records.items():
        df = pd.DataFrame(rows)

        if "TimeUS" in df.columns:
            df = df.sort_values(
                "TimeUS"
            ).reset_index(drop=True)

        datasets[msg_type] = df

    return datasets
