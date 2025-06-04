
# ─── Streamlit must be first ────────────────────────────────────────────────
import streamlit as st
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
from agents import Runner
load_dotenv()
# -----------------------------------------------------------------------------
# 1. CONFIGURATION & CREDENTIALS
# -----------------------------------------------------------------------------
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
os.environ["OPENAI_BASE_URL"] = st.secrets["OPENAI_BASE_URL"]
st.set_page_config(page_title="Taxy.ai", layout="wide", page_icon=":oncoming_taxi:")
APP_TITLE: Final[str] = "🧮 Taxy.ai – GenAI Tax Preparation"
LOG_DIR: Final[Path] = Path("logs")
RAW_INPUT_DIR: Final[Path] = Path("Data/Intermediate/Client_Input_RAW")
SYSTEM_PROMPT: Final[str] = "You are a helpful tax preparation assistant."

# -----------------------------------------------------------------------------
# 2. SETUP LOGGER
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"taxy_app_{datetime.now():%Y%m%d}.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)
# ─────────────────────────────────────────────────────────────────────────────
# 3. Initialize State
# ─────────────────────────────────────────────────────────────────────────────
# — Initialize session state —
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "You are helpful assistant for tax preparations."},
        {"role": "assistant", "content": "👋 Hi there! Please upload your W-2 to get started..."}
    ]
if 'model' not in st.session_state:
    st.session_state['model'] = OpenAI()
# store the retrieved context so follow-ups can refer back
if "context" not in st.session_state:
    st.session_state.context = [
        {"role": "system", "content": "You are helpful assistant for tax preparations."},
    ]

# ─────────────────────────────────────────────────────────────────────────────
# 4. Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📑 Your documents")
    if st.button("🔄 New conversation"):
        st.session_state.messages = [
            {"role": "system", "content": "You are helpful assistant for tax preparations."},
            {"role": "assistant", "content": "👋 Hi there! Please upload your W-2 to get started..."}
        ]
        st.session_state.context =  [
            {"role": "system", "content": "You are helpful assistant for tax preparations."},
        ]
        st.session_state.chat_history =[
            {"role": "system", "content": "You are helpful assistant for tax preparations."},
        ]
    st.selectbox(
        "OpenAI Model",
        options=["gpt-4.1", "o3", "o3-mini"],
        key="model_name"
    )
    uploaded_file_pdf = st.file_uploader(
        "Upload your W-2",
        type=["pdf"],
        help="Select a W-2 PDF to begin OCR and tax assistance.",
        key="w2_uploader",
    )

# ─────────────────────────────────────────────────────────────────────────────
# 4. Sidebar
# ─────────────────────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


if uploaded_file_pdf is not None:
    with st.chat_message("assistant"):
        st.markdown(
            "Thank you for uploading your W-2. We are processing your document and will get back to you shortly."
        )
    st.session_state.messages.append({"role": "assistant", "content": "Thank you for uploading your W-2. We are processing your document and will get back to you shortly."})

    os.makedirs(RAW_INPUT_DIR, exist_ok=True)
    save_path = os.path.join(RAW_INPUT_DIR, uploaded_file_pdf.name)
    try:
        if os.path.exists(save_path):
            os.remove(save_path)
    except Exception as e:
        logging.error(f"Failed to delete file {save_path}: {e}")
        # 4. Write the PDF bytes to disk
    with open(save_path, "wb") as f:
        f.write(uploaded_file_pdf.getbuffer())
    logger.info("Saved upload to %s", save_path)
    chunk_content = DocumentOCR(uploaded_file_pdf.name)

    result = asyncio.run(Runner.run(UserProfileAgent, chunk_content))
    st.session_state.context.append({"role": "user", "content": "# Employee W-2 Form \n {}".format(chunk_content)})
    logger.info("Final output: %s", result.final_output)
    while result.final_output.complete == False:
        r = {}
        for question in result.final_output.missing_questions:
            with st.chat_message("assistant"):
                st.markdown(question)
            st.stop()
            # wait for the user's reply
            answer = st.chat_input(
                "Type your answer…",
                key=f"missing_q_{question}"
            )
            if answer:
                r[question] = answer
                with st.chat_message("user"):
                    st.markdown(answer)
                st.rerun()
        # Adjusted Profile
        adj_message = "# Additional User Information\n" + str(dict(r)) + "\n" + "# Original User Information\n" + str(result.final_output)
        result = asyncio.run(Runner.run(
            UserProfileAgent, adj_message
        ))
    st.markdown(str(result.final_output))



# ─────────────────────────────────────────────────────────────────────────────
# 6. Conversation
# ─────────────────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Type your question…", key="Main_Chat_Input"):
    # 1) Record and display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.context.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        stream = st.session_state['model'].chat.completions.create(
            model=st.session_state['model_name'] ,
            messages=st.session_state['context'],
            stream=True
        )
        response = st.write_stream(stream)
    st.session_state['context'].append({"role": "assistant", "content": response})
    st.session_state['messages'].append({"role": "assistant", "content": response})