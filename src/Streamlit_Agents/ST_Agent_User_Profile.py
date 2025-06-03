# src/Agent_User_Profile.py
import os
from typing import Any, Dict, Literal

from pydantic import BaseModel, Field, EmailStr
from agents import Agent, Runner, function_tool
from dotenv import load_dotenv
import streamlit as st

load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

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
@function_tool
def ask_social_security_number() -> Dict[str, str]:
    ssn_value = st.session_state.get("tool_ask_ssn", "").strip()
    return {"Social_Security_Number": ssn_value}


@function_tool
def ask_name() -> Dict[str, str]:
    name_value = st.session_state.get("tool_ask_name", "").strip()
    return {"Name": name_value}


@function_tool
def ask_email() -> Dict[str, str]:
    email_value = st.session_state.get("tool_ask_email", "").strip()
    return {"Email": email_value}


@function_tool
def ask_filing_status() -> Dict[str, str]:
    filing_value = st.session_state.get("tool_ask_filing_status", "").strip()
    return {"filingStatus": filing_value}


@function_tool
def ask_dependents() -> Dict[str, int]:
    deps_value = st.session_state.get("tool_ask_dependents", 0)
    try:
        return {"dependents": int(deps_value)}
    except Exception:
        return {"dependents": 0}


@function_tool
def ask_address() -> Dict[str, str]:
    addr_value = st.session_state.get("tool_ask_address", "").strip()
    return {"address": addr_value}


@function_tool
def ask_state() -> Dict[str, str]:
    state_value = st.session_state.get("tool_ask_state", "").strip()
    return {"state": state_value}


@function_tool
def ask_occupation() -> Dict[str, str]:
    occ_value = st.session_state.get("tool_ask_occupation", "").strip()
    return {"Occupation": occ_value}


@function_tool
def ask_spouse_name() -> Dict[str, Dict[str, Any]]:
    spouse_name = st.session_state.get("tool_ask_spouse_name", "").strip()
    return {"spouse": {"name": spouse_name}}


@function_tool
def ask_spouse_occupation() -> Dict[str, Dict[str, Any]]:
    spouse_occ = st.session_state.get("tool_ask_spouse_occupation", "").strip()
    return {"spouse": {"occupation": spouse_occ}}


@function_tool
def ask_spouse_birthyear() -> Dict[str, Dict[str, Any]]:
    byear = st.session_state.get("tool_ask_spouse_birthyear", None)
    try:
        return {"spouse": {"birthYear": int(byear)}}
    except Exception:
        return {"spouse": {"birthYear": 0}}


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
    model="gpt-4.1-mini",
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
