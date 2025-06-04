import asyncio
from agents import (
    Agent,
    GuardrailFunctionOutput,
    InputGuardrailTripwireTriggered,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
    input_guardrail,
    output_guardrail,
    FileSearchTool,
)
import os
from dotenv import load_dotenv

from IPython.display import display, Markdown
import nest_asyncio
import pandas as pd
from typing import Literal
from pydantic import BaseModel, Field

class Form1040Profile(BaseModel):
    Employee_SSN : str
    "Employee Social Security Number"
    TaxYear : int
    "Tax Year from Employee W-2"
    Employer: str
    "Employer Name from the Employee W-2"
    Employer_EIN: str
    "Employer Identification Number (EIN) from the Employee W-2"
    Employee_Name: str
    "Employee Name from the Employee W-2"
    Employee_DOB: str
    "Employee Date of Birth from the Employee W-2"
    Income: str
    ''' Total Employer Income'''
    Deduction: float
    '''What is the Total Employee Deductions?'''
    Deduction_Reasoning: str
    "What is the reasoning behind the Deductions? Give a detailed breakdown."
    taxCredits: float
    ''' What is the Total Tax Credits?'''
    taxCredits_Reasoning: str
    "What is the reasoning behind the Tax Credits? Give a detailed breakdown."
    taxWithheld: float
    '''What is the total tax withheld?'''
    taxWithheld_Reasoning: str
    "What is the reasoning behind the tax withheld? Give a detailed breakdown."
    federalTaxDue: float
    '''Federal tax due'''
    federalTaxDue_Reasoning: str
    "What is the reasoning behind the federal tax due? Give a detailed breakdown."
    refundAmount: float
    '''What is the Refund Amount (if positive)?'''
    refundAmount_Reasoning: str
    "What is the reasoning behind the Refund Amount? Give a detailed breakdown."
    amountOwed: float
    '''What is the Amount owed (if positive)?'''
    amountOwed_Reasoning: str
    "What is the reasoning behind the Amount owed? Give a detailed breakdown."
    questions: str
    "Any additional questions about the employee to accurately conduct calculations. Questions should be single item, detailed, and clear?"
    score: Literal["High", "Medium", "Low"]
    "Score for the user profile based on the questions and answers"

TaxAgent = Agent(
        name="TaxAgent",
        instructions="You are are preparing the 1040 tax document for an employee. Loop through and double-check everything.",
        output_type=Form1040Profile,
        model="o3",
        tools=[
            FileSearchTool(
                max_num_results=40,
                vector_store_ids=["vs_683dca6814108191a83ccb974fff986d"],
                include_search_results=True,
            )
        ],
    )

TaxAgentResponse = Agent(
    name="TaxAgentResponse",
        instructions="Create a succinct and well structure message explaining the tax results and reasoning over major components.",
        model="gpt-4.1",
        output_type=str,
)