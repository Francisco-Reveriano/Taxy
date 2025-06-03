import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from src.Streamlit_Agents.ST_Widgets import *
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
# Load environment variables from .env
load_dotenv()

# -----------------------------------------------------------------------------
# CONFIGURATION & CREDENTIALS
# -----------------------------------------------------------------------------
os.environ['OPENAI_API_KEY'] = os.getenv("mck_openai_api_key")
os.environ['OPENAI_BASE_URL'] = os.getenv("mck_openai_base_url")
st.set_page_config(layout="wide", page_title="Taxy.ai")

# -----------------------------------------------------------------------------
# SESSION STATE INITIALIZATION (do this before any reference to conversation)
# -----------------------------------------------------------------------------
# Initialize the OpenAI client if it doesn't exist
if "client" not in st.session_state:
    st.session_state.client = OpenAI(
        api_key=st.secrets["OPENAI_API_KEY"],
        base_url=st.secrets["OPENAI_BASE_URL"],
    )

# Initialize the chat history list
st.session_state.setdefault(
    "conversation",
    [
        {
            "role": "system",
            "content": "You are a helpful tax preparation assistant.",
        }
    ],
)

# -----------------------------------------------------------------------------
# SIDEBAR CONTROLS (now it's safe to reference st.session_state.conversation)
# -----------------------------------------------------------------------------
st.sidebar.title("Model Options")
st.sidebar.button(
    "New Conversation",
    type="primary",
    on_click=reset_conversation,   # calls helper above
)

st.sidebar.selectbox(
    "OpenAI Model",
    options=["gpt-4.1", "gpt-4.1-mini", "o3", "o3-mini"],
    key="model_name",
)

# -----------------------------------------------------------------------------
# MAIN CHAT INTERFACE: Display Past Messages
# -----------------------------------------------------------------------------
st.title("Taxy.ai")

for msg in st.session_state.conversation[1:]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -----------------------------------------------------------------------------
# If no file has been uploaded yet, show an assistant message prompting upload
# -----------------------------------------------------------------------------
if "uploaded_file_name" not in st.session_state:
    with st.chat_message("assistant"):
        st.markdown("👋 Please upload your W-2 form (PDF) so I can help you get started...")
    uploaded_file_pdf = st.file_uploader(
        "Upload your W-2:",
        type=["pdf"],
        help="Select a PDF of your W-2 to begin OCR and tax assistance."
    )
    if uploaded_file_pdf is not None:
        st.session_state.uploaded_file_name = uploaded_file_pdf.name
else:
    # Keep the uploader visible in case they want to change the upload later
    uploaded_file_pdf = st.file_uploader(
        "Upload your W-2:",
        type=["pdf"],
        help="Select a PDF of your W-2 to begin OCR and tax assistance.",
        key="persistent_uploader"
    )

# -----------------------------------------------------------------------------
# Once a file is present, process it
# -----------------------------------------------------------------------------
if uploaded_file_pdf is not None:
    # 1. Make sure the directory exists
    intermediate_data_path = "Data/Intermediate/Client_Input_RAW"
    os.makedirs(intermediate_data_path, exist_ok=True)

    # 2. Build the full save path using the original filename
    save_path = os.path.join(intermediate_data_path, uploaded_file_pdf.name)

    # 3. If a file with the same name already exists, remove it
    try:
        if os.path.exists(save_path):
            os.remove(save_path)
    except Exception as e:
        logging.error(f"Failed to delete file {save_path}: {e}")

    # 4. Write the PDF bytes to disk
    with open(save_path, "wb") as f:
        f.write(uploaded_file_pdf.getbuffer())

    # 5. Confirm saving and perform OCR
    with st.chat_message("assistant"):
        st.markdown("✅ Performing OCR now…")
        st.session_state.conversation.append(
            {"role": "assistant", "content": "✅ Performing OCR now…"}
        )
        chunk_content_string = DocumentOCR(uploaded_file_pdf.name)

    with st.chat_message("assistant"):
        st.markdown('''📝 OCR complete!''')
        st.session_state.conversation.append(
            {"role": "assistant", "content": "📝 OCR complete!"}
        )

    # (h) 1st pass: run UserProfileAgent on the raw text to extract whatever fields it can
    with st.chat_message("assistant"):
        st.markdown("🔎 Extracting profile fields from OCR…")
        partial_profile = asyncio.run(Runner.run(UserProfileAgent, chunk_content_string))
        st.session_state.conversation.append(
            {"role": "assistant", "content": partial_profile.final_output}
        )