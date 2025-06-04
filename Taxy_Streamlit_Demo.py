# ─── Streamlit must be first ────────────────────────────────────────────────
import streamlit as st
st.set_page_config(page_title="Taxy.ai",
                   layout="wide",
                   page_icon=":oncoming_taxi:")

# ─── Standard library & third-party imports ────────────────────────────────
import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Final

from dotenv import load_dotenv
from openai import OpenAI

from src.Agent_OCR import DocumentOCR
from src.Streamlit_Agents.ST_Agent_User_Profile import UserProfileAgent
from src.Streamlit_Agents.ST_Question_Function import run_question_flow  # takes a `state` dict! :contentReference[oaicite:0]{index=0}
from agents import Runner

load_dotenv()

# ─── Config & constants ────────────────────────────────────────────────────
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
os.environ["OPENAI_BASE_URL"] = st.secrets["OPENAI_BASE_URL"]

APP_TITLE:   Final[str] = "🧮 Taxy.ai – GenAI Tax Preparation"
LOG_DIR:     Final[Path] = Path("logs")
RAW_INPUT:   Final[Path] = Path("Data/Intermediate/Client_Input_RAW")

# ─── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"taxy_app_{datetime.now():%Y%m%d}.log",
                            encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ─── Session-state initialisation ──────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system",
         "content": "You are a helpful assistant for tax preparations."},
        {"role": "assistant",
         "content": "👋 Hi there! Please upload your W-2 to get started…"},
    ]

if "context" not in st.session_state:
    st.session_state.context = [
        {"role": "system",
         "content": "You are a helpful assistant for tax preparations."},
    ]

# ─── Sidebar (upload & controls) ───────────────────────────────────────────
with st.sidebar:
    st.header("📑 Your documents")

    # “New conversation” – wipe everything
    if st.button("🔄 New conversation"):
        for k in ("messages", "context", "profile_result", "followup_state"):
            st.session_state.pop(k, None)
        st.rerun()

    st.selectbox("OpenAI model",
                 options=["gpt-4.1","gpt-4.1-mini", "o4-mini", "o3", "o3-mini"],
                 key="model_name")

    uploaded_file = st.file_uploader(
        "Upload your W-2",
        type=["pdf"],
        help="Select a W-2 PDF to begin OCR and tax assistance.",
        key="w2_uploader",
    )

# ─── Redisplay prior chat history ──────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ─── ONE-TIME document ingestion & first agent run ─────────────────────────
if uploaded_file is not None and "profile_result" not in st.session_state:
    with st.chat_message("assistant"):
        st.markdown("Thank you for uploading your W-2. "
                    "We’re processing it now…")

    # Persist the chat message
    st.session_state.messages.append({
        "role": "assistant",
        "content": "Thank you for uploading your W-2. "
                   "We’re processing it now…",
    })

    # Save the PDF to disk
    RAW_INPUT.mkdir(parents=True, exist_ok=True)
    save_path = RAW_INPUT / uploaded_file.name
    save_path.write_bytes(uploaded_file.getbuffer())
    logger.info("Saved upload to %s", save_path)

    # OCR + first agent pass
    with st.spinner("Running OCR and extracting your profile…"):
        doc_text = DocumentOCR(uploaded_file.name)
        first_pass = asyncio.run(Runner.run(UserProfileAgent, doc_text))

    # Cache the result so subsequent reruns don’t redo heavy work
    st.session_state.profile_result  = first_pass
    st.session_state.context.append({"role": "assistant", "content": "# First User Profile\n" + str(dict(first_pass.final_output))})
    logger.info("First User Profile: %s", str(dict(first_pass.final_output)))
    st.session_state.followup_state  = {}   # initialise the Q&A cursor

    # Keep doc text in context so later completions can see it
    st.session_state.context.append(
        {"role": "user", "content": "# Employee W-2 Form\n" + doc_text})

# ─── Follow-up Q&A loop (runs every rerun once we have a profile) ──────────
if "profile_result" in st.session_state:
    result = st.session_state.profile_result

    if not result.final_output.complete:
        qa_state = st.session_state["followup_state"]

        answers = run_question_flow(
            questions=result.final_output.missing_questions,
            state=qa_state,
            model=st.session_state.model_name,
        )  # → returns dict *only* after last answer

        if answers is not None:
            logger.info("Collected follow-up answers: %s", answers)

            adjusted_msg = (
                "# Additional User Information\n"
                f"{answers}\n"
                "# Original User Information\n"
                f"{result.final_output}"
            )

            # Second pass with the extra info
            with st.spinner("Updating your profile with the new answers…"):
                st.session_state.profile_result = asyncio.run(
                    Runner.run(UserProfileAgent, adjusted_msg)
                )
            # Update Context
            st.session_state.context.append(
                {"role": "assistant", "content": "# Full User Profile\n" + str(dict(st.session_state.profile_result.final_output))})
            logger.info("Full User Profile: %s", str(dict(st.session_state.profile_result.final_output)))
            # reset follow-up state for any future rounds
            st.session_state.followup_state = {}
            st.rerun()   # show the updated state immediately

    else:
        # Profile complete – show summary once
        with st.chat_message("assistant"):
            st.markdown("✅ I now have all the information I need! "
                        "Here is your completed profile:")

