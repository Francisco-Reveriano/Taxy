import streamlit as st

def reset_conversation() -> None:
    # ── 1.1 purge or re-initialise only the keys you care about ──────────
    st.session_state["conversation"]        = [{
        "role": "system",
        "content": "You are a helpful tax preparation assistant."
    }]
    st.session_state["api_conversation"]    = st.session_state["conversation"].copy()
    st.session_state["download_buffer"]     = None
    st.session_state["download_available"]  = False
    st.session_state["uploaded_file_pdf"] = None
    st.session_state.pop("uploaded_file_name", None)       # forget W-2
    # ── 1.2 hard reset *everything else* (optional) ───────
    st.session_state.clear()