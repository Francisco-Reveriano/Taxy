import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional, Dict
load_dotenv()

def run_question_flow(
    questions: list[str],
    *,
    state: dict,                    # << NEW parameter
    model: str = "gpt-3.5-turbo"
):
    """
    Presents a linear, chat-style Q&A flow in Streamlit.
    Returns a dict once the last question is answered; otherwise None.
    """

    client = OpenAI()

    # ─── 1. Pull or initialise local fields from the passed-in dict ─────────
    idx        = state.get("idx", 0)
    responses  = state.setdefault("responses", [])
    messages   = state.setdefault("messages", [])

    # ─── 2. Redisplay existing messages ─────────────────────────────────────
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ─── 3. If finished, return summary ─────────────────────────────────────
    if idx >= len(questions):
        return {questions[i]: responses[i] for i in range(len(questions))}

    # ─── 4. Ask the current question (only once) ────────────────────────────
    if len(messages) <= 2 * idx:
        raw_q = questions[idx]
        rewrite_stream = client.chat.completions.create(
            model=model,
            stream=True,
            messages=[
                {"role": "system",
                 "content": "You are a helpful question rewriter. "
                            "Rewrite each question in a friendly, conversational tone."},
                {"role": "user", "content": raw_q},
            ],
        )
        with st.chat_message("assistant"):
            rewritten = st.write_stream(rewrite_stream)
        messages.append({"role": "assistant", "content": rewritten})

    # ─── 5. Capture user input ──────────────────────────────────────────────
    if user := st.chat_input("Type your answer here...", key=f"answer_{idx}"):
        messages.append({"role": "user", "content": user})
        responses.append(user)
        state["idx"] = idx + 1          # advance cursor
        st.rerun()

    return None
