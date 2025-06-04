import os
import asyncio
from typing import Any, Dict, Literal
from pydantic import BaseModel, Field, EmailStr
from agents import Agent, Runner, function_tool
from dotenv import load_dotenv

# 1. Load environment variables
load_dotenv()


# 2. Define Pydantic schemas
class FollowUpSpouseProfile(BaseModel):
    name: str = Field(..., description="Name of the spouse")
    occupation: str = Field(..., description="Occupation of the spouse")
    birthYear: int = Field(..., description="Birth year of the spouse")

class FollowUpUserProfile(BaseModel):
    Social_Security_Number: str = Field(..., description="Employee Social Security Number")
    Name: str = Field(..., description="Full Name of the Employee")
    Email: EmailStr = Field(..., description="Email Address of the Employee")
    filingStatus: Literal[
        "Single",
        "Married Filing Jointly",
        "Married Filing Separately",
        "Head of Household",
        "Qualifying Widow(er)"
    ] = Field(..., description="Tax filing status of the Employee")
    dependents: int = Field(..., description="Number of dependents of the Employee")
    address: str = Field(..., description="Mailing Address of the Employee")
    state: str = Field(..., description="State of residence of the Employee")
    Occupation: str = Field(..., description="Occupation of the Employee")
    spouse: FollowUpSpouseProfile = Field(..., description="Spouse Information (if married)")

class SpouseProfile(BaseModel):
    name : str
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
    filingStatus: Literal['Single', "Married Filing Jointly", "Married Filing Separately", "Head of Household", "Qualifying Widow(er)"]
    '''Tax filling status of the Employee'''
    dependents: int
    '''Number of dependents of the Employee'''
    address: str
    '''Mailing Address of the Employee'''
    state: str
    '''State of residence of the Employee'''
    Occupation: str
    '''Occupation of the Employee'''
    spouse:SpouseProfile
    '''Spouse Information (if married)'''

# 3. Create function tools with valid JSON Schema-compatible signatures
@function_tool
def ask_social_security_number() -> Dict[str, str]:
    """Prompt for Social Security Number."""
    user_input = input("Enter your Social Security Number: ").strip()
    return {"Social_Security_Number": user_input}

@function_tool
def ask_name() -> Dict[str, str]:
    """Prompt for Full Name."""
    user_input = input("Enter your full name: ").strip()
    return {"Name": user_input}

@function_tool
def ask_email() -> Dict[str, str]:
    """Prompt for Email Address with validation."""
    user_input = input("Enter your email address: ").strip()
    return {"Email": user_input}

@function_tool
def ask_filing_status() -> Dict[str, str]:
    """Prompt for Filing Status."""
    options = [
        "Single",
        "Married Filing Jointly",
        "Married Filing Separately",
        "Head of Household",
        "Qualifying Widow(er)"
    ]
    while True:
        user_input = input(f"Enter your filing status {options}: ").strip()
        if user_input in options:
            return {"filingStatus": user_input}
        print("Invalid option. Please choose one of the listed statuses.")

@function_tool
def ask_dependents() -> Dict[str, int]:
    """Prompt for Number of Dependents with validation."""
    while True:
        user_input = input("Enter number of dependents: ").strip()
        try:
            return {"dependents": int(user_input)}
        except ValueError:
            print("Invalid number. Please enter an integer.")

@function_tool
def ask_address() -> Dict[str, str]:
    """Prompt for Mailing Address."""
    user_input = input("Enter your mailing address: ").strip()
    return {"address": user_input}

@function_tool
def ask_state() -> Dict[str, str]:
    """Prompt for State of Residence."""
    user_input = input("Enter your state of residence: ").strip()
    return {"state": user_input}

@function_tool
def ask_occupation() -> Dict[str, str]:
    """Prompt for Occupation of the Employee."""
    user_input = input("Enter your occupation: ").strip()
    return {"Occupation": user_input}

@function_tool
def ask_spouse_name() -> Dict[str, Dict[str, Any]]:
    """Prompt for Spouse Name."""
    user_input = input("Enter your spouse’s name: ").strip()
    return {"spouse": {"name": user_input}}

@function_tool
def ask_spouse_occupation() -> Dict[str, Dict[str, Any]]:
    """Prompt for Spouse Occupation."""
    user_input = input("Enter your spouse’s occupation: ").strip()
    return {"spouse": {"occupation": user_input}}

@function_tool
def ask_spouse_birthyear() -> Dict[str, Dict[str, Any]]:
    """Prompt for Spouse Birth Year."""
    while True:
        user_input = input("Enter your spouse’s birth year: ").strip()
        try:
            return {"spouse": {"birthYear": int(user_input)}}
        except ValueError:
            print("Invalid year. Please enter a valid integer.")


PROMPT = '''
You are a helpful tax agent. You thoroughly read the document and provide the required information.
'''
UserProfileAgent = Agent(
        name="UserProfileAgent",
        instructions=PROMPT,
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
3. If the filing status is “Married Filing Jointly” or “Married Filing Separately” or “Qualifying Widow(er)”, then you must also collect spouse information by invoking:
   • ask_spouse_name
   • ask_spouse_occupation
   • ask_spouse_birthyear
4. Validate all inputs. If a value fails (e.g., non-integer for dependents), call the same tool again.
5. Once all fields satisfy the UserProfile schema, return a JSON object matching UserProfile exactly.
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
