import asyncio
from agents import (
    Agent,
    GuardrailFunctionOutput,
    InputGuardrailTripwireTriggered,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
    input_guardrail,
    output_guardrail
)
import os
from dotenv import load_dotenv

from IPython.display import display, Markdown
import nest_asyncio
import pandas as pd
from typing import Literal
from pydantic import BaseModel, Field
from src.Agent_OCR import load_from_json
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("mck_openai_api_key") or os.getenv("OPENAI_API_KEY", "")
os.environ["OPENAI_BASE_URL"] = os.getenv("mck_openai_base_url") or os.getenv("OPENAI_BASE_URL", "")

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
    complete: Literal[True, False]
    ''' Provide a boolean value indicating whether all required fields are complete.'''
    complete_reasoning: str
    ''' Reasoning behind the completion of the user profile.'''
    missing_questions: list[str] = []
    ''' List of missing questions in the user profile.'''

class UserProfileOutput(BaseModel):
    reasoning: str
    ''' Reasoning for the guardrail output.'''
    is_complete: bool
    ''' Are all attributes in the user profile complete?'''
    missing_questions: list[str]
    ''' List of missing questions in the user profile.'''

PROMPT = '''
You are a helpful tax agent. You thoroughly read the document and provide the required information.
'''
UserProfileAgent = Agent(
        name="UserProfileAgent",
        instructions=PROMPT,
        model="o3",
        output_type=UserProfile,
        )

