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

federal_tax_agent = Agent(
    name="Federal_Tax_Agent",
    instructions="You are an expert file-search tax agent for federal tax documents.",
    output_type=str,
        model="o3",
        tools=[
            FileSearchTool(
                max_num_results=40,
                vector_store_ids=["vs_683dca6814108191a83ccb974fff986d"],
                include_search_results=True,
            )
        ],
)

illinois_tax_agent = Agent(
    name="Illinois_Tax_Agent",
    instructions="You are an expert file-search tax agent for the state of Illinois",
    output_type=str,
        model="o3",
        tools=[
            FileSearchTool(
                max_num_results=40,
                vector_store_ids=["vs_6841d1063e788191aed6d433023b92e5"],
                include_search_results=True,
            )
        ],
)

TaxAgentPrompt = '''
        You are an expert tax advisor. You thoroughly read the document and provide a detailed but clear answer to the user.
        If asked for tax details regarding Federal or State taxes, you call the relevant tools.
'''
TaxAgent = Agent(
        name="TaxAgent",
        instructions=TaxAgentPrompt,
        output_type=str,
        model="o3",
        tools=[
            federal_tax_agent.as_tool(
                tool_name="Federal_Tax_Agent",
                tool_description="Use this tool to search for federal tax documents.",
            ),
            illinois_tax_agent.as_tool(
                tool_name="Illinois_Tax_Agent",
                tool_description="Use this tool to search for the state of Illinois specific tax documents.",
            )
        ],
    )

def call_TaxAgent(model:str) -> Agent:
    TaxAgent = Agent(
        name="TaxAgent",
        instructions=TaxAgentPrompt,
        output_type=str,
        model=model,
        tools=[
            federal_tax_agent.as_tool(
                tool_name="Federal_Tax_Agent",
                tool_description="Use this tool to search for federal tax documents.",
            ),
            illinois_tax_agent.as_tool(
                tool_name="Illinois_Tax_Agent",
                tool_description="Use this tool to search for the state of Illinois specific tax documents.",
            )
        ],
    )
    return TaxAgent