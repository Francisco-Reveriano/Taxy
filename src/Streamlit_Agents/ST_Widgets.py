import streamlit as st

def reset_conversation() -> None:
    """Clear **all** stateful variables so the next interaction truly starts fresh."""
    # Reset chat history to the single system prompt
    st.session_state.conversation = [
        {
            "role": "system",
            "content": "You are a helpful tax preparation assistant.",
        },
        {
            "role": "assistant",
            "content": "How can I help you get started with your tax preparation?"
        }
    ]

    # Remove any stored filename or upload widget content
    st.session_state.pop("uploaded_file_name", None)
    st.session_state["w2_uploader"] = None  # Clears the file_uploader widget

    # Optionally wipe any other custom keys you might have added later
    for key in [
        "ocr_text",
        "profile_extracted",
        "model_name",
    ]:
        st.session_state.pop(key, None)