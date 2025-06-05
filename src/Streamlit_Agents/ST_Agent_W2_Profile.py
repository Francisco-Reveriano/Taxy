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

class W2Profile(BaseModel):
    """
    Represents a W-2 Profile containing details of an employee's tax-related
    information derived from their W-2 form.

    This class is used to encapsulate and organize the details from an employee's
    W-2 tax form, including employer information, wages, taxes, and other
    necessary data for tax processing or record-keeping purposes.

    :ivar TaxYear: Tax year from the employee's W-2.
    :type TaxYear: int
    :ivar Employer: Employer name from the employee's W-2.
    :type Employer: str
    :ivar Employer_EIN: Employer Identification Number (EIN) from the employee's W-2.
    :type Employer_EIN: str
    :ivar Employee_Name: Employee name from the employee's W-2.
    :type Employee_Name: str
    :ivar Employee_SSN: Employee Social Security Number from the employee's W-2.
    :type Employee_SSN: str
    :ivar Employee_DOB: Employee date of birth from the employee's W-2.
    :type Employee_DOB: str
    :ivar Wages_Income: Employee wages and income from the employee's W-2.
    :type Wages_Income: float
    :ivar Federal_Taxes_Withheld: Employee federal taxes withheld from the employee's W-2.
    :type Federal_Taxes_Withheld: float
    :ivar Filling_Status: Employee filing status from the employee's W-2.
    :type Filling_Status: Literal['Single', 'Married Filing Jointly', 'Married Filing
        Separately', 'Head of Household', 'Qualifying Widow(er)']
    :ivar State_Information: Employee state information, such as state wages and withheld amounts,
        from the employee's W-2.
    :type State_Information: str
    :ivar Questions: Any questions or unclear information about the employee from the W-2.
    :type Questions: str
    :ivar Score: Scoring for the user profile, evaluating based on questions and answers.
    :type Score: Literal['High', 'Medium', 'Low']
    """
    TaxYear : int
    "Tax Year from Employee W-2"
    Employer: str
    "Employer Name from the Employee W-2"
    Employer_EIN: str
    "Employer Identification Number (EIN) from the Employee W-2"
    Employee_Name: str
    "Employee Name from the Employee W-2"
    Employee_SSN: str
    "Employee Social Security Number from the Employee W-2"
    Employee_DOB: str
    "Employee Date of Birth from the Employee W-2"
    Employee_DoB: str
    "Employee Date of Birth from the Employee W-2"
    Wages_Income: float
    "Employee Wages and Income from the Employee W-2"
    Federal_Taxes_Withheld: float
    "Employee Federal Taxes Withheld from the Employee W-2"
    Filling_Status: Literal['Single', "Married Filing Jointly", "Married Filing Separately", "Head of Household", "Qualifying Widow(er)"]
    "Employee Filing Status from the Employee W-2"
    State_Information: str
    "Employee State Information (e.g., States and wages withold by the state)  from the Employee W-2"
    Questions: str
    "Any questions about the employee from the Employee W-2? Or information that is not clear"
    Score: Literal["High", "Medium", "Low"]
    "Score for the user profile based on the questions and answers"


PROMPT_W2_Profile_Agent = '''
You are a helpful tax agent. You thoroughly read the document and provide the required information.
'''

W2_Profile_Agent = Agent(
        name="W2ProfileAgent",
        instructions=PROMPT_W2_Profile_Agent,
        model="o3",
        output_type=W2Profile,
        )
W2_Profile_Table_Agent = Agent(
    name="W2ProfileTableAgent",
        instructions="Create well constructed Markdown table from the provided user profile. Add icons to each field. Skip 'Questions' and 'Score'. Double-check the response and make sure you return nothing but the table.",
        model="gpt-4.1-mini",
        output_type=str,
)