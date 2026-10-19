"""Streamlit recording inventory with status and filename filters."""

import pandas as pd
import streamlit as st


REQUIRED_COLUMNS = (
    "LogFile",
    "Status",
    "ArmedSessions",
    "ActivitySegments",
    "DiagnosticStatus",
)


def render_recording_inventory(master_index: pd.DataFrame) -> None:
    """Show searchable, status-filtered recording metadata."""
    missing = [col for col in REQUIRED_COLUMNS if col not in master_index.columns]
    if missing:
        st.error(f"Missing inventory columns: {', '.join(missing)}")
        return

    st.subheader("Recording Inventory")

    options = sorted(master_index["Status"].dropna().astype(str).unique().tolist())
    filter_col, search_col = st.columns([1, 2])
    with filter_col:
        status = st.selectbox("Processing status", ["All statuses", *options])
    with search_col:
        filename_query = st.text_input(
            "Search recording filename", placeholder="e.g. 2026-07-02 or 77"
        ).strip()

    filtered = master_index.copy()
    if status != "All statuses":
        filtered = filtered.loc[filtered["Status"] == status]
    if filename_query:
        filtered = filtered.loc[
            filtered["LogFile"].astype("string").str.contains(
                filename_query, case=False, regex=False, na=False
            )
        ]

    st.caption(f"Showing {len(filtered)} of {len(master_index)} recordings")
    st.dataframe(
        filtered[list(REQUIRED_COLUMNS)],
        use_container_width=True,
        hide_index=True,
    )
    if filtered.empty:
        st.info("No recordings match those filters. Try another status or search term.")


    # Only recordings with reconstructed sessions can open in Session Explorer.
    eligible = filtered.loc[
        filtered["Status"].eq("SUCCESS")
        & pd.to_numeric(filtered["ArmedSessions"], errors="coerce").gt(0),
        "LogFile",
    ].dropna().astype(str).sort_values().unique().tolist()

    st.markdown("#### Open Recording in Session Explorer")
    if not eligible:
        st.info("No successfully analyzed recordings match the current filters.")
        return

    selected_log = st.selectbox(
        "Choose a recording to explore",
        eligible,
        key="inventory_recording_to_open",
    )

    if st.button("Open in Session Explorer", type="primary"):
        # app.py consumes this request before constructing sidebar widgets.
        st.session_state["pending_session_recording"] = selected_log
        st.rerun()
