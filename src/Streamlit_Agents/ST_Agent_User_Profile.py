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

class SpouseProfile(BaseModel):
    """
    Represents a profile of a spouse.

    This class holds information about a spouse, including their name,
    occupation, and birth year. It is designed to encapsulate and provide
    a consistent structure for spouse data in the application.

    :ivar name: Name of the spouse.
    :type name: str
    :ivar occupation: Occupation of the spouse.
    :type occupation: str
    :ivar birthYear: Birth year of the spouse.
    :type birthYear: int
    """
    name : str
    "Name of the spouse"
    occupation: str
    "Occupation of the spouse"
    birthYear: int
    "Birth year of the spouse"

class UserProfile(BaseModel):
    """
    Represents a user profile for managing personal and tax-related information.

    This class contains detailed attributes of a user profile such as personal
    information, mailing address, tax details, and others. It is primarily used
    to store and validate the completeness of user data for compliance or
    processing tasks.

    :ivar Social_Security_Number: Employee Social Security Number.
    :type Social_Security_Number: str
    :ivar Name: Full Name of the Employee.
    :type Name: str
    :ivar DoB: Date of Birth of the Employee.
    :type DoB: str
    :ivar Email: Email Address of the Employee.
    :type Email: str
    :ivar filingStatus: Tax filing status of the Employee.
    :type filingStatus: Literal['Single', 'Married Filing Jointly',
                                 'Married Filing Separately', 'Head of Household',
                                 'Qualifying Widow(er)']
    :ivar dependents: Number of dependents of the Employee.
    :type dependents: int
    :ivar address: Mailing Address of the Employee.
    :type address: str
    :ivar state: State of residence of the Employee.
    :type state: str
    :ivar Occupation: Occupation of the Employee.
    :type Occupation: str
    :ivar spouse: Spouse Information (if married).
    :type spouse: SpouseProfile
    :ivar complete: Provide a boolean value indicating whether all required fields
        are complete.
    :type complete: Literal[True, False]
    :ivar complete_reasoning: Reasoning behind the completion of the user profile.
    :type complete_reasoning: str
    :ivar missing_questions: List of missing questions in the user profile.
    :type missing_questions: list[str]
    """
    Social_Security_Number: str
    '''Employee Social Security Number'''
    Name: str
    '''Full Name of the Employee'''
    DoB: str
    '''Date of Birth of the Employee'''
    Email: str
    '''Email Address of the Employee'''
    filingStatus: Literal['Single', "Married Filing Jointly", "Married Filing Separately", "Head of Household", "Qualifying Widow(er)"]
    '''Tax filling status of the Employee'''
    dependents: int
    '''Number of dependents of the Employee'''
    Income: float
    ''' Total Employer Wages, Tips, and Other Compensation'''
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
    """
    Handles the output of user profile validation and reasoning.

    This class is utilized to represent the results of a validation process
    for a user profile. It provides detailed reasoning about the validation outcome,
    indicates whether the profile is complete, and lists any missing questions
    if the profile is incomplete.

    :ivar reasoning: Reasoning for the guardrail output.
    :type reasoning: str
    :ivar is_complete: Indicates whether all attributes in the user profile are
        complete.
    :type is_complete: bool
    :ivar missing_questions: List of missing questions in the user profile if
        it is incomplete.
    :type missing_questions: list[str]
    """
    reasoning: str
    ''' Reasoning for the guardrail output.'''
    is_complete: bool
    ''' Are all attributes in the user profile complete?'''
    missing_questions: list[str]
    ''' List of missing questions in the user profile.'''

PROMPT_UserProfile_Agent = '''
You are a helpful tax agent. You thoroughly read the document and provide the required information, reasoning, and follow-up questions.
Double-check that the results are correct from the OCR output.  
'''
UserProfileAgent = Agent(
        name="UserProfileAgent",
        instructions=PROMPT_UserProfile_Agent,
        model="o3",
        output_type=UserProfile,
        )

