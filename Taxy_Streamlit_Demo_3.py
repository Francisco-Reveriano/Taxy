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
from millify import millify
from src.Agent_OCR import DocumentOCR
from src.Streamlit_Agents.ST_Agent_User_Profile import UserProfileAgent
from src.Streamlit_Agents.ST_Question_Function import run_question_flow
from src.Streamlit_Agents.ST_Agent_W2_Profile import W2_Profile_Agent, W2_Profile_Table_Agent
from src.Streamlit_Agents.ST_Agent_Tax_Agent import *
from src.Streamlit_Agents.ST_Agent_General_Response import call_TaxAgent
from agents import Runner, set_trace_processors
from weave.integrations.openai_agents.openai_agents import WeaveTracingProcessor
import weave
import tempfile
load_dotenv()

# ─── Config & constants ────────────────────────────────────────────────────
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

APP_TITLE:   Final[str] = "🧮 Taxy.ai – GenAI Tax Preparation"
LOG_DIR:     Final[Path] = Path("logs")
RAW_INPUT:   Final[Path] = Path("Data/Intermediate/Client_Input_RAW")

weave.init("openai-agents")
set_trace_processors([WeaveTracingProcessor()])

# ─── Logging ────────────────────────────────────────────────────────────────
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

# ─── Session-state initialization ──────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant for tax preparations."
        },
        {
            "role": "assistant",
            "content": "👋 Hi there! Please upload your W-2 to get started…"
        },
    ]

if "context" not in st.session_state:
    st.session_state.context = [
        {
            "role": "system",
            "content": "You are a helpful assistant for tax preparations."
        },
    ]

if "total_income" not in st.session_state:
    st.session_state.total_income = 0.00
if "total_tax_withheld" not in st.session_state:
    st.session_state.total_tax_withheld = 0.00
if "total_deduction" not in st.session_state:
    st.session_state.total_deduction = 0.00
if "total_tax_due" not in st.session_state:
    st.session_state.total_tax_due = 0.00
if "total_tax_credits" not in st.session_state:
    st.session_state.total_tax_credits = 0.00
if "total_refunds" not in st.session_state:
    st.session_state.total_refunds = 0.00

# ─── New flag to prevent the tax block from re-executing ────────────────────
if "tax_done" not in st.session_state:
    st.session_state.tax_done = False

# ─── Sidebar (upload & controls) ───────────────────────────────────────────
with st.sidebar:
    st.header("📑 Your documents")

    # “New conversation” – clear state
    if st.button("🔄 New conversation"):
        for k in ("messages", "context", "profile_result", "followup_state", "tax_done"):
            st.session_state.pop(k, None)
        st.rerun()

    st.selectbox(
        "OpenAI model",
        options=["gpt-4.1", "gpt-4.1-mini", "o4-mini", "o3", "o3-mini"],
        key="model_name"
    )

    uploaded_file = st.file_uploader(
        "Upload your W-2",
        type=["pdf"],
        help="Select a W-2 PDF to begin OCR and tax assistance.",
        key="w2_uploader",
    )

    st.subheader("Financial Summary")
    # Placeholder for metrics (will render once tax_done == True)
    metrics_placeholder = st.empty()

# ─── Redisplay prior chat history ──────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ─── ONE-TIME document ingestion & first agent run ─────────────────────────
if uploaded_file is not None and "profile_result" not in st.session_state:
    with st.chat_message("assistant"):
        st.markdown("Thank you for uploading your W-2. We’re processing it now…")

    # Persist the chat message
    st.session_state.messages.append({
        "role": "assistant",
        "content": "Thank you for uploading your W-2. We’re processing it now…"
    })

    # Save the PDF to disk
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.getbuffer())
        temp_pdf_path = Path(tmp.name)
    logger.info("Saved upload to %s", temp_pdf_path)
    st.session_state["uploaded_path"] = str(temp_pdf_path)
    # ➌ OCR + first agent pass
    with st.spinner("Running OCR and extracting your profile…"):
        # DocumentOCR now receives the *full* path
        doc_text = DocumentOCR(str(temp_pdf_path))
        st.session_state["W2_Form"] = doc_text
        first_pass = asyncio.run(Runner.run(UserProfileAgent, doc_text))

    # Cache the result so subsequent reruns don’t redo heavy work
    st.session_state.profile_result = first_pass
    st.session_state.context.append({
        "role": "assistant",
        "content": "# First User Profile\n" + str(dict(first_pass.final_output))
    })
    logger.info("First User Profile: %s", str(dict(first_pass.final_output)))

    st.session_state.followup_state = {}
    st.session_state.context.append({
        "role": "user",
        "content": "# Employee W-2 Form\n" + doc_text
    })

    st.rerun()

# ─── Follow-up Q&A loop (runs every rerun once we have a profile) ──────────
if "profile_result" in st.session_state:
    result = st.session_state.profile_result

    # If profile is incomplete, ask follow-up questions
    if not result.final_output.complete:
        qa_state = st.session_state["followup_state"]
        qa_container = st.container()
        with qa_container:
            answers = run_question_flow(
                questions=result.final_output.missing_questions,
                state=qa_state,
                model=st.session_state.model_name,
            )  # → returns dict *only* after last answer

        if answers is not None:
            qa_container.empty()
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
            st.session_state.context.append({
                "role": "assistant",
                "content": "# Full User Profile\n" +
                           str(dict(st.session_state.profile_result.final_output))
            })
            st.session_state["Full_User_Profile"] = dict(
                st.session_state.profile_result.final_output
            )
            logger.info(
                "Full User Profile: %s",
                str(dict(st.session_state.profile_result.final_output))
            )

            # reset follow-up state for any future rounds
            st.session_state.followup_state = {}

            st.rerun()

    # Once the profile is complete and we haven't already run the tax‐block…
    elif result.final_output.complete and not st.session_state.tax_done:
        # --- Build W2 Profile and display it ---
        updated_message = (
            "# Full User Profile\n"
            + str(st.session_state["Full_User_Profile"])
            + "\n\n# Employee W-2\n"
            + st.session_state["W2_Form"]
        )
        w2_profile = asyncio.run(Runner.run(W2_Profile_Agent, updated_message))
        logger.info("W2 Profile: %s", str(w2_profile.final_output))
        st.session_state["W2_Profile"] = str(w2_profile.final_output)

        w2_table = asyncio.run(Runner.run(
            W2_Profile_Table_Agent,
            str(w2_profile.final_output)
        ))
        logger.info("W2 Profile Table: %s", str(w2_table.final_output))

        with st.chat_message("assistant"):
            st.markdown("✅ I now have all the information I need! Here is your completed profile:")
            st.markdown(w2_table.final_output)

        st.session_state.messages.append({
            "role": "assistant",
            "content": w2_table.final_output
        })

        # --- Calculate Tax Profile ---
        tax_input_message = (
            "# Complete Employee Profile\n"
            f"{st.session_state['Full_User_Profile']}\n\n"
            "# Complete W-2 Profile\n"
            f"{st.session_state['W2_Profile']}\n\n"
            "# Employee W-2\n"
            f"{st.session_state['W2_Form']}"
        )
        tax_result = asyncio.run(Runner.run(TaxAgent, tax_input_message))

        st.session_state.total_income = tax_result.final_output.Income
        st.session_state.total_tax_withheld = tax_result.final_output.taxWithheld
        st.session_state.total_deduction = tax_result.final_output.Deduction
        st.session_state.total_tax_credits = tax_result.final_output.taxCredits
        st.session_state.total_tax_due = tax_result.final_output.federalTaxDue
        st.session_state.total_refunds = tax_result.final_output.refundAmount

        # Append tax profile data to context
        st.session_state.context.append({
            "role": "assistant",
            "content": "# Tax Profile\n" + str(tax_result.final_output)
        })

        # --- Generate a well‐structured tax report and display it ---
        client = OpenAI()
        rewrite_stream = client.chat.completions.create(
            model=st.session_state.model_name,
            stream=True,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Create a well-structured report that explains the tax results. "
                        "Your response should reason through the major components contributing "
                        "to the outcome (e.g., income, deductions, credits, filing status), "
                        "using straightforward and professional language. Do not include any "
                        "additional commentary or disclaimers outside the message itself."
                    )
                },
                {
                    "role": "user",
                    "content": str(tax_result.final_output)
                },
            ],
        )
        with st.chat_message("assistant"):
            rewritten = st.write_stream(rewrite_stream)

        st.session_state.messages.append({
            "role": "assistant",
            "content": rewritten
        })
        st.session_state.context.append({
            "role": "assistant",
            "content": rewritten
        })

        # Mark tax block as done so it does not run again
        st.session_state.tax_done = True

# ─── Render Financial Metrics if tax is done ─────────────────────────────────
if st.session_state.tax_done:
    with metrics_placeholder.container():
        a, b = st.columns(2)
        a.metric("Income ($)", millify(st.session_state.total_income, precision=1))
        b.metric("Tax Withheld ($)", millify(st.session_state.total_tax_withheld, precision=1))
        c, d = st.columns(2)
        c.metric("Deductions ($)", millify(st.session_state.total_deduction, precision=1))
        d.metric("Tax Credits ($)", millify(st.session_state.total_tax_credits, precision=1))
        st.metric("Tax Due ($)", millify(st.session_state.total_tax_due, precision=2))
        st.metric("Refunds ($)", millify(st.session_state.total_refunds, precision=2))

# ─── User follow‐up on tax results (Q&A) ────────────────────────────────────
# Show this input once the tax report has been generated
if st.session_state.tax_done:
    user_prompt = st.chat_input("Ask me anything about your tax result…")
    if user_prompt:
        # 1) Display the user question in the Streamlit chat UI
        with st.chat_message("user"):
            st.markdown(user_prompt)

        # 2) Append the user question to both messages and context
        st.session_state.messages.append({
            "role": "user",
            "content": user_prompt
        })
        st.session_state.context.append({
            "role": "user",
            "content": user_prompt
        })

        # 3) Call the general TaxAgent for follow‐ups
        TaxAgent = call_TaxAgent(st.session_state.model_name)
        general_response = asyncio.run(Runner.run(TaxAgent, user_prompt))

        with st.chat_message("assistant"):
            rewritten = st.write_stream(general_response.final_output)

        st.session_state.messages.append({
            "role": "assistant",
            "content": general_response.final_output
        })
        st.session_state.context.append({
            "role": "assistant",
            "content": general_response.final_output
        })

        st.rerun()
