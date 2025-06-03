# src/Agent_User_Profile.py
import os
from typing import Any, Dict, Literal

from pydantic import BaseModel, Field, EmailStr
from agents import Agent, Runner, function_tool
from dotenv import load_dotenv
import streamlit as st

load_dotenv()
# ——————————————————————————————————————————————————————————————————————————————
# 1. Pydantic schemas
# ——————————————————————————————————————————————————————————————————————————————
class FollowUpSpouseProfile(BaseModel):
    name: str = Field(..., description="Name of the spouse")
    occupation: str = Field(..., description="Occupation of the spouse")
    birthYear: int = Field(..., description="Birth year of the spouse")


class FollowUpUserProfile(BaseModel):
    Social_Security_Number: str = Field(
        ..., description="Employee Social Security Number"
    )
    Name: str = Field(..., description="Full Name of the Employee")
    Email: EmailStr = Field(..., description="Email Address of the Employee")
    filingStatus: Literal[
        "Single",
        "Married Filing Jointly",
        "Married Filing Separately",
        "Head of Household",
        "Qualifying Widow(er)",
    ] = Field(..., description="Tax filing status of the Employee")
    dependents: int = Field(..., description="Number of dependents of the Employee")
    address: str = Field(..., description="Mailing Address of the Employee")
    state: str = Field(..., description="State of residence of the Employee")
    Occupation: str = Field(..., description="Occupation of the Employee")
    spouse: FollowUpSpouseProfile = Field(..., description="Spouse Information (if married)")


class SpouseProfile(BaseModel):
    name: str
    "Name of the spouse"
    occupation: str
    "Occupation of the spouse"
    birthYear: int
    "Birth year of the spouse"


class UserProfile(BaseModel):
    Social_Security_Number: str
    '''Employee Social Security Number'''
    Name: str
    '''Full Name of the Employee'''
    Email: str
    '''Email Address of the Employee'''
    filingStatus: Literal[
        'Single',
        "Married Filing Jointly",
        "Married Filing Separately",
        "Head of Household",
        "Qualifying Widow(er)",
    ]
    '''Tax filing status of the Employee'''
    dependents: int
    '''Number of dependents of the Employee'''
    address: str
    '''Mailing Address of the Employee'''
    state: str
    '''State of residence of the Employee'''
    Occupation: str
    '''Occupation of the Employee'''
    spouse: SpouseProfile
    '''Spouse Information (if married)'''


# ——————————————————————————————————————————————————————————————————————————————
# 2. “Function tool” helpers that read from st.session_state instead of input()
# ——————————————————————————————————————————————————————————————————————————————
# --- 2. “Function tool” helpers that show a prompt right in the UI -----------
# Each helper renders the widget the FIRST time it is called.
# On the next rerun, the stored value is returned to the agent.
# ——————————————————————————————————————————————————————————————————————————————
# 2. “Function tool” helpers – conversational (no widgets)
# ——————————————————————————————————————————————————————————————————————————————
import streamlit as st
from datetime import datetime

def _prompt_once(key: str, assistant_msg: str, placeholder: str = "Type your answer…") -> str | None:
    """
    Helper: ask a question exactly once, store the reply, and return it on
    every subsequent rerun so the agent can keep going.
    """
    if key in st.session_state:               # Already answered
        return st.session_state[key]

    # Show the assistant question only the first time
    if f"{key}_prompted" not in st.session_state:
        st.chat_message("assistant").write(assistant_msg)
        st.session_state[f"{key}_prompted"] = True

    # Chat input appears only at the very bottom of the page
    user_reply = st.chat_input(placeholder=placeholder)
    if user_reply:
        st.session_state[key] = user_reply.strip()
        return st.session_state[key]

    # Wait for the user to reply (this stops the script until next rerun)
    st.stop()


@function_tool
def ask_social_security_number() -> Dict[str, str]:
    """Conversation: collect SSN."""
    ssn = _prompt_once(
        key="ssn_value",
        assistant_msg="🔑 Could you share your **Social Security Number**?",
    )
    return {"Social_Security_Number": ssn}


@function_tool
def ask_name() -> Dict[str, str]:
    """Conversation: collect full name."""
    name = _prompt_once(
        key="name_value",
        assistant_msg="🪪 Great! What’s your **full legal name**?",
    )
    return {"Name": name}


@function_tool
def ask_email() -> Dict[str, str]:
    """Conversation: collect e-mail."""
    email = _prompt_once(
        key="email_value",
        assistant_msg="📧 What e-mail address should we use for correspondence?",
    )
    return {"Email": email}


@function_tool
def ask_filing_status() -> Dict[str, str]:
    """Conversation: collect filing status (show allowed options)."""
    filing = _prompt_once(
        key="filing_status_value",
        assistant_msg=(
            "💍 Which **filing status** applies?\n"
            "• Single\n• Married Filing Jointly\n• Married Filing Separately\n"
            "• Head of Household\n• Qualifying Widow(er)"
        ),
        placeholder="Type one of the options above…",
    )
    return {"filingStatus": filing}


@function_tool
def ask_dependents() -> Dict[str, int]:
    """Conversation: collect number of dependents (integer)."""
    deps = _prompt_once(
        key="dependents_value",
        assistant_msg="👶 How many **dependents** do you claim?",
    )
    # Basic validation – keep asking until an int
    try:
        return {"dependents": int(deps)}
    except ValueError:
        del st.session_state["dependents_value"]  # reset and ask again
        st.chat_message("assistant").write("Please enter a whole-number (0, 1, 2 …).")
        st.stop()


@function_tool
def ask_address() -> Dict[str, str]:
    addr = _prompt_once(
        key="address_value",
        assistant_msg="📬 What’s your **mailing address** (street, city, ZIP)?",
    )
    return {"address": addr}


@function_tool
def ask_state() -> Dict[str, str]:
    state = _prompt_once(
        key="state_value",
        assistant_msg="🏛️ In which **state** do you reside?",
    )
    return {"state": state}


@function_tool
def ask_occupation() -> Dict[str, str]:
    job = _prompt_once(
        key="occupation_value",
        assistant_msg="💼 What’s your current **occupation**?",
    )
    return {"Occupation": job}


# ---------------- Spouse questions (only when required) ----------------------
@function_tool
def ask_spouse_name() -> Dict[str, Dict[str, Any]]:
    s_name = _prompt_once(
        key="spouse_name_value",
        assistant_msg="👥 What is your spouse’s **name**?",
    )
    return {"spouse": {"name": s_name}}


@function_tool
def ask_spouse_occupation() -> Dict[str, Dict[str, Any]]:
    s_job = _prompt_once(
        key="spouse_job_value",
        assistant_msg="👥 What is your spouse’s **occupation**?",
    )
    return {"spouse": {"occupation": s_job}}


@function_tool
def ask_spouse_birthyear() -> Dict[str, Dict[str, Any]]:
    s_year = _prompt_once(
        key="spouse_year_value",
        assistant_msg="👥 What is your spouse’s **birth year**?",
        placeholder="e.g. 1988",
    )
    try:
        y = int(s_year)
        this_year = datetime.now().year
        if 1900 <= y <= this_year:
            return {"spouse": {"birthYear": y}}
        raise ValueError
    except ValueError:
        del st.session_state["spouse_year_value"]
        st.chat_message("assistant").write(f"Please enter a year between 1900 and {this_year}.")
        st.stop()



# ——————————————————————————————————————————————————————————————————————————————
# 3. The two Agent definitions
# ——————————————————————————————————————————————————————————————————————————————
PROMPT_MAIN = """
You are a helpful tax agent. You thoroughly read the document and provide the required information.
"""

UserProfileAgent = Agent(
    name="UserProfileAgent",
    instructions=PROMPT_MAIN,
    model="gpt-4.1-mini",
    output_type=UserProfile,
)

UserProfileFollowUpAgent = Agent(
    name="UserProfileFollowUpAgent",
    instructions="""
You are a helpful tax agent. Your task is to collect all required fields for the UserProfile schema.

1. Identify which UserProfile fields are missing.
2. For each missing field, call the corresponding tool:
   • ask_social_security_number
   • ask_name
   • ask_email
   • ask_filing_status
   • ask_dependents
   • ask_address
   • ask_state
   • ask_occupation
3. If the filing status is one of:
   – Married Filing Jointly
   – Married Filing Separately
   – Qualifying Widow(er)
   then you must also collect spouse information by invoking:
   • ask_spouse_name
   • ask_spouse_occupation
   • ask_spouse_birthyear
4. Once all fields satisfy UserProfile (including correct data types),
   return a JSON object matching the UserProfile schema exactly.
""",
    model="gpt-4.1",
    tools=[
        ask_social_security_number,
        ask_name,
        ask_email,
        ask_filing_status,
        ask_dependents,
        ask_address,
        ask_state,
        ask_occupation,
        ask_spouse_name,
        ask_spouse_occupation,
        ask_spouse_birthyear,
    ],
    output_type=FollowUpUserProfile,
)
