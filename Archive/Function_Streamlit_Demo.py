# streamlit_app.py

import streamlit as st
from src.Streamlit_Agents.ST_Question_Function import run_question_flow

QUESTIONS = [
    "What is your preferred email address?",
    "What is your correct filing status for 2010 (Single, Married Filing Jointly, etc.)?",
    "How many dependents, if any, are you claiming?",
    "What is your occupation/title with Hall Ltd Group?",
    "If married, please provide your spouse’s full name, occupation, and birth year."
]

st.set_page_config(page_title="My Q&A Flow", layout="wide")
st.title("Welcome to the Q&A Flow")

# ─── 1. Invoke the question flow. It will initialize and update `st.session_state.messages` internally.
summary = run_question_flow(QUESTIONS)

# ─── 2. When all questions are answered, `summary` is a dict. Otherwise it’s None.
if summary:
    st.write("## Thank you! Here are your responses:")
    for q, a in summary.items():
        st.write(f"**Q:** {q}  \n**A:** {a}")

    # (OPTIONAL) If you want to inspect the raw session_state.messages from `question_flow.py`:
    st.write("---")
    st.write("### Full chat history (for debugging):")
    for m in st.session_state.messages:
        role = m["role"]
        content = m["content"]
        st.write(f"- **{role}**: {content}")
