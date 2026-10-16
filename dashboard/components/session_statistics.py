import pandas as pd
import streamlit as st


def render_session_statistics(sessions: pd.DataFrame):
    st.subheader("📊 Session Statistics")

    total_sessions = len(sessions)
    mean_duration = sessions["ArmedDurationSec"].mean()
    mean_activity = sessions["ActivityRatio"].mean() * 100

    col1, col2, col3 = st.columns(3)

    col1.metric("Armed Sessions", total_sessions)
    col2.metric("Mean Armed Duration", f"{mean_duration:.2f} s")
    col3.metric("Mean Motor Activity", f"{mean_activity:.1f}%")

    st.markdown("#### Session Classification Distribution")

    classification_counts = (
        sessions["SessionClassification"]
        .value_counts()
        .rename_axis("Classification")
        .reset_index(name="Sessions")
    )

    st.bar_chart(
        classification_counts,
        x="Classification",
        y="Sessions",
    )

    st.markdown("#### Armed-Session Duration Distribution")

    st.bar_chart(
        sessions["ArmedDurationSec"].value_counts(
            bins=20
        ).sort_index()
    )