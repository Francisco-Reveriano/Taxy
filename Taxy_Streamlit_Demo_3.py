# ─── Streamlit must be first ─────────────────────────────────────────────
import streamlit as st
st.set_page_config(page_title="Taxy.ai",
                   layout="wide",
                   page_icon=":oncoming_taxi:")

# ─── Standard library & third-party imports ───────────────────────────────
import asyncio
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

# ─── Config & constants ───────────────────────────────────────────────────
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

APP_TITLE: Final[str] = "🧮 Taxy.ai – GenAI Tax Preparation"
RAW_INPUT: Final[Path] = Path("Data/Intermediate/Client_Input_RAW")

weave.init("openai-agents")
set_trace_processors([WeaveTracingProcessor()])

# ─── Session-state initialization ─────────────────────────────────────────
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

for key in (
    "total_income",
    "total_tax_withheld",
    "total_deduction",
    "total_tax_credits",
    "total_tax_due",
    "total_refunds",
):
    st.session_state.setdefault(key, 0.0)

# Prevent the tax block from re-executing
st.session_state.setdefault("tax_done", False)

# ─── Sidebar (upload & controls) ──────────────────────────────────────────
with st.sidebar:
    st.header("📑 Your documents")

    if st.button("🔄 New conversation"):
        for k in ("messages", "context", "profile_result", "followup_state", "tax_done"):
            st.session_state.pop(k, None)
        st.rerun()

    st.selectbox(
        "OpenAI model",
        options=["gpt-4.1", "gpt-4.1-mini", "o4-mini", "o3", "o3-mini"],
        key="model_name",
    )

    uploaded_file = st.file_uploader(
        "Upload your W-2",
        type=["pdf"],
        help="Select a W-2 PDF to begin OCR and tax assistance.",
        key="w2_uploader",
    )

    st.subheader("Financial Summary")
    metrics_placeholder = st.empty()

# ─── Redisplay prior chat history ─────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ─── One-time document ingestion & first agent run ────────────────────────
if uploaded_file is not None and "profile_result" not in st.session_state:
    with st.chat_message("assistant"):
        st.markdown("Thank you for uploading your W-2. We’re processing it now…")

    st.session_state.messages.append({
        "role": "assistant",
        "content": "Thank you for uploading your W-2. We’re processing it now…"
    })

    # Save upload to a temporary file that survives reruns
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.getbuffer())
        temp_pdf_path = Path(tmp.name)

    st.session_state["uploaded_path"] = str(temp_pdf_path)

    # OCR + first agent pass
    with st.spinner("Running OCR and extracting your profile…"):
        doc_text = DocumentOCR(str(temp_pdf_path))
        st.session_state["W2_Form"] = doc_text
        first_pass = asyncio.run(Runner.run(UserProfileAgent, doc_text))

    st.session_state.profile_result = first_pass
    st.session_state.context.append({
        "role": "assistant",
        "content": "# First User Profile\n" + str(dict(first_pass.final_output))
    })

    st.session_state.followup_state = {}
    st.session_state.context.append({
        "role": "user",
        "content": "# Employee W-2 Form\n" + doc_text
    })

    st.rerun()

# ─── Follow-up Q&A loop ────────────────────────────────────────────────────
if "profile_result" in st.session_state:
    result = st.session_state.profile_result

    if not result.final_output.complete:
        qa_state = st.session_state["followup_state"]
        qa_container = st.container()
        with qa_container:
            answers = run_question_flow(
                questions=result.final_output.missing_questions,
                state=qa_state,
                model=st.session_state.model_name,
            )

        if answers is not None:
            qa_container.empty()

            adjusted_msg = (
                "# Additional User Information\n"
                f"{answers}\n"
                "# Original User Information\n"
                f"{result.final_output}"
            )

            with st.spinner("Updating your profile with the new answers…"):
                st.session_state.profile_result = asyncio.run(
                    Runner.run(UserProfileAgent, adjusted_msg)
                )

            st.session_state.context.append({
                "role": "assistant",
                "content": "# Full User Profile\n" +
                           str(dict(st.session_state.profile_result.final_output))
            })
            st.session_state["Full_User_Profile"] = dict(
                st.session_state.profile_result.final_output
            )

            st.session_state.followup_state = {}
            st.rerun()

    elif result.final_output.complete and not st.session_state.tax_done:
        # Build W-2 profile
        updated_message = (
            "# Full User Profile\n"
            + str(st.session_state["Full_User_Profile"])
            + "\n\n# Employee W-2\n"
            + st.session_state["W2_Form"]
        )
        w2_profile = asyncio.run(Runner.run(W2_Profile_Agent, updated_message))
        st.session_state["W2_Profile"] = str(w2_profile.final_output)

        w2_table = asyncio.run(
            Runner.run(W2_Profile_Table_Agent, str(w2_profile.final_output))
        )

        with st.chat_message("assistant"):
            st.markdown("✅ I now have all the information I need! Here is your completed profile:")
            st.markdown(w2_table.final_output)

        st.session_state.messages.append({
            "role": "assistant",
            "content": w2_table.final_output
        })

        # Calculate tax profile
        tax_input_message = (
            "# Complete Employee Profile\n"
            f"{st.session_state['Full_User_Profile']}\n\n"
            "# Complete W-2 Profile\n"
            f"{st.session_state['W2_Profile']}\n\n"
            "# Employee W-2\n"
            f"{st.session_state['W2_Form']}"
        )
        tax_result = asyncio.run(Runner.run(TaxAgent, tax_input_message))

        st.session_state.total_income        = tax_result.final_output.Income
        st.session_state.total_tax_withheld  = tax_result.final_output.taxWithheld
        st.session_state.total_deduction     = tax_result.final_output.Deduction
        st.session_state.total_tax_credits   = tax_result.final_output.taxCredits
        st.session_state.total_tax_due       = tax_result.final_output.federalTaxDue
        st.session_state.total_refunds       = tax_result.final_output.refundAmount

        st.session_state.context.append({
            "role": "assistant",
            "content": "# Tax Profile\n" + str(tax_result.final_output)
        })

        # Generate a concise tax report
        client = OpenAI()
        rewrite_stream = client.chat.completions.create(
            model=st.session_state.model_name,
            stream=True,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Create a well-structured report that explains the tax results. "
                        "Reason through the major components contributing to the outcome "
                        "(income, deductions, credits, filing status) in clear, professional language. "
                        "Do not add any extra commentary or disclaimers."
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

        st.session_state.tax_done = True

# ─── Financial metrics ─────────────────────────────────────────────────────
if st.session_state.tax_done:
    with metrics_placeholder.container():
        a, b = st.columns(2)
        a.metric("Income ($)",          millify(st.session_state.total_income, precision=1))
        b.metric("Tax Withheld ($)",    millify(st.session_state.total_tax_withheld, precision=1))
        c, d = st.columns(2)
        c.metric("Deductions ($)",      millify(st.session_state.total_deduction, precision=1))
        d.metric("Tax Credits ($)",     millify(st.session_state.total_tax_credits, precision=1))
        st.metric("Tax Due ($)",        millify(st.session_state.total_tax_due, precision=2))
        st.metric("Refunds ($)",        millify(st.session_state.total_refunds, precision=2))

# ─── User follow-up Q&A ────────────────────────────────────────────────────
if st.session_state.tax_done:
    user_prompt = st.chat_input("Ask me anything about your tax result…")
    if user_prompt:
        with st.chat_message("user"):
            st.markdown(user_prompt)

        st.session_state.messages.append({
            "role": "user",
            "content": user_prompt
        })
        st.session_state.context.append({
            "role": "user",
            "content": user_prompt
        })

        TaxAgent = call_TaxAgent(st.session_state.model_name)
        general_response = asyncio.run(Runner.run(TaxAgent, user_prompt))

        with st.chat_message("assistant"):
            rewritten = st.markdown(general_response.final_output)

        st.session_state.messages.append({
            "role": "assistant",
            "content": general_response.final_output
        })
        st.session_state.context.append({
            "role": "assistant",
            "content": general_response.final_output
        })

        st.rerun()
