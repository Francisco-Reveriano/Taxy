import streamlit as st
import pandas as pd
import os
from datetime import datetime
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT AGENTS / APP-SPECIFIC IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
from src.Streamlit_Agents.ST_Widgets import *        # noqa: F403  (streamlit widget helpers)
from src.Agent_OCR import DocumentOCR
from src.Streamlit_Agents.ST_Agent_User_Profile import (
    UserProfileAgent,
    UserProfileFollowUpAgent,
    FollowUpUserProfile,
)
from openai import OpenAI
import asyncio
import logging
from agents import Agent, FileSearchTool, Runner, WebSearchTool

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,                # set to DEBUG for more verbosity
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(LOG_DIR, f"taxy_app_{datetime.now().strftime('%Y%m%d')}.log"),
            encoding="utf-8"
        ),
        logging.StreamHandler(),       # also prints to Streamlit backend console
    ],
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# ENVIRONMENT & CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv()
os.environ["OPENAI_API_KEY"]  = os.getenv("mck_openai_api_key")
os.environ["OPENAI_BASE_URL"] = os.getenv("mck_openai_base_url")

st.set_page_config(layout="wide", page_title="Taxy.ai")
logger.info("Streamlit page configured.")

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG & SESSION INIT
# ─────────────────────────────────────────────────────────────────────────────
def reset_conversation() -> None:
    """Wipe everything so the next interaction is truly fresh."""
    st.session_state.clear()
    st.session_state["conversation"] = [
        {"role": "system", "content": "You are a helpful tax preparation assistant."}
    ]

if "conversation" not in st.session_state:
    st.session_state.conversation = [
        {"role": "system", "content": "You are a helpful tax preparation assistant."}
    ]
if "file_processed" not in st.session_state:
    st.session_state.file_processed = False

# OpenAI client (lazy load)
if "client" not in st.session_state:
    st.session_state.client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_BASE_URL"],
    )

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR – upload + controls
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📑 Your documents")

    if st.button("🔄 New conversation"):
        reset_conversation()

    uploaded_file_pdf = st.file_uploader(
        "Upload your W-2",
        type=["pdf"],
        help="Select a W-2 PDF to begin OCR and tax assistance.",
        key="w2_uploader",
    )

# ─────────────────────────────────────────────────────────────────────────────
# MAIN CHAT UI
# ─────────────────────────────────────────────────────────────────────────────
st.title("🧮 Taxy.ai – GenAI Tax Preparation")

# Replay previous messages (skip the system prompt)
for msg in st.session_state.conversation[1:]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ─────────────────────────────────────────────────────────────────────────────
# 1️⃣  No file yet – prompt the user
# ─────────────────────────────────────────────────────────────────────────────
if uploaded_file_pdf is None:
    with st.chat_message("assistant"):
        st.markdown(
            "👋 Please upload your W-2 PDF from the sidebar so I can start helping."
        )
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# 2️⃣  We have a file but haven’t processed it this run
# ─────────────────────────────────────────────────────────────────────────────
if not st.session_state.file_processed:
    # Save uploaded file to a temp folder
    intermediate_data_path = "Data/Intermediate/Client_Input_RAW"
    os.makedirs(intermediate_data_path, exist_ok=True)
    # Build the full save path using the original filename
    save_path = os.path.join(intermediate_data_path, uploaded_file_pdf.name)
    # If a file with the same name already exists, remove it
    try:
        if os.path.exists(save_path):
            os.remove(save_path)
    except Exception as e:
        logging.error(f"Failed to delete file {save_path}: {e}")

    # 4. Write the PDF bytes to disk
    with open(save_path, "wb") as f:
        f.write(uploaded_file_pdf.getbuffer())
    logger.info("Saved upload to %s", save_path)

    # ---------- OCR ----------------------------------------------------------
    with st.chat_message("assistant"):
        st.markdown("🔎 Running OCR on your W-2…")
    chunk_content = DocumentOCR(uploaded_file_pdf.name)

    # ---------- PROFILE EXTRACTION (partial) ---------------------------------
    with st.chat_message("assistant"):
        st.markdown("📋 Extracting the obvious fields…")
    partial_profile = asyncio.run(
        Runner.run(UserProfileAgent, chunk_content)
    )
    st.session_state["partial_profile"] = partial_profile.final_output
    st.session_state.conversation.append(
        {"role": "assistant", "content": str(partial_profile.final_output)}
    )
    logger.info("Partial profile extracted: %s", partial_profile.final_output)

    # ---------- FOLLOW-UP PASS 1 (renders widgets) ---------------------------
    with st.chat_message("assistant"):
        st.markdown("📝 Asking follow-up questions… (widgets appear above)")
    _ = asyncio.run(
        Runner.run(
            UserProfileFollowUpAgent,
            str(dict(st.session_state["partial_profile"])),
        )
    )

    # Tell the user what to do next
    st.session_state.conversation.append(
        {
            "role": "assistant",
            "content": "👇 Please fill in any missing details in the form fields "
                       "now visible, then click **Continue** below.",
        }
    )

    # Add the “Continue” button to wait for user input
    if st.button("✅ Continue"):
        st.session_state["ready_for_full_profile"] = True

    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# 3️⃣  The user clicked “Continue” – run follow-up pass 2
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.get("ready_for_full_profile") and not st.session_state.file_processed:
    with st.chat_message("assistant"):
        st.markdown("🔄 Processing your answers…")

    full_profile_run = asyncio.run(
        Runner.run(
            UserProfileFollowUpAgent,
            str(dict(st.session_state["partial_profile"])),
        )
    )
    st.session_state["full_user_profile"] = full_profile_run.final_output
    st.session_state.conversation.append(
        {"role": "assistant", "content": str(full_profile_run.final_output)}
    )
    logger.info("Full profile assembled: %s", full_profile_run.final_output)

    # Mark done so we don’t repeat this block on every rerun
    st.session_state.file_processed = True
    st.success("✅ All done! Your complete profile is now ready.")
