# question_flow.py

import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional, Dict

load_dotenv()

def run_question_flow(
    questions: list[str],
    *,
    model: str = "gpt-3.5-turbo"
) -> Optional[Dict[str, str]]:
    """
    Presents a linear, chat-style Q&A flow in Streamlit.
    - `questions`: list of raw question strings to ask.
    - `model`: OpenAI model name for rewriting each question.
    Returns a dict mapping each question to its answer once complete, otherwise None.
    """

    client = OpenAI()

    # ─── 1. Initialize/Reset Session State ────────────────────────────────────
    # NOTE: This is the only place where we ever initialize `st.session_state.messages`.
    if "question_index" not in st.session_state:
        st.session_state.question_index = 0

    if "responses" not in st.session_state:
        st.session_state.responses = []

    if "messages" not in st.session_state:
        # Create the single shared list for chat‐history
        st.session_state.messages = []

    # ─── 2. Redisplay Existing Chat History ──────────────────────────────────
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ─── 3. Determine Current Question Index ─────────────────────────────────
    idx = st.session_state.question_index

    # ─── 4. If All Questions Were Answered, Return Summary ───────────────────
    if idx >= len(questions):
        summary = {
            questions[i]: st.session_state.responses[i]
            for i in range(len(questions))
        }
        return summary

    # ─── 5. Only Rewrite & Render the Question Once ──────────────────────────
    # If len(messages) <= 2*idx, we haven’t asked question #idx yet.
    if len(st.session_state.messages) <= 2 * idx:
        raw_q = questions[idx]
        rewrite_stream = client.chat.completions.create(
            model=model,
            stream=True,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful question rewriter. "
                        "Rewrite each question in a friendly, conversational tone."
                    )
                },
                {"role": "user", "content": raw_q}
            ]
        )
        with st.chat_message("assistant"):
            rewritten = st.write_stream(rewrite_stream)

        # **This single append updates the shared list**, visible to `streamlit_app.py`
        st.session_state.messages.append(
            {"role": "assistant", "content": rewritten}
        )

    # ─── 6. Capture the User’s Answer to the Current Question ─────────────────
    if user_input := st.chat_input("Type your answer here..."):
        # 6.1 Display user’s answer in chat format
        st.session_state.messages.append({"role": "user", "content": user_input})

        # 6.2 Store the raw answer
        st.session_state.responses.append(user_input)

        # 6.3 Advance to next question
        st.session_state.question_index += 1

        # 6.4 Force a rerun so the next question appears immediately
        st.experimental_rerun()

    return None

