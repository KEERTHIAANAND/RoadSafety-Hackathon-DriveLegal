import os
from langchain_groq import ChatGroq
from langchain.agents import create_agent
from app.config import LLM_MODEL_NAME, GROQ_API_KEY
from app.agent.tools import (
    search_national_laws,
    search_state_laws,
    calculate_challan,
    resolve_location,
    format_citation,
    search_web_fallback
)
from app.agent.prompts import SYSTEM_PROMPT

def get_agent_executor():
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set in environment variables. Agent will not work.")

    # 1. Initialize LLM
    llm = ChatGroq(
        model=LLM_MODEL_NAME,
        temperature=0,
        groq_api_key=GROQ_API_KEY
    )

    # 2. Create agent
    tools = [
        search_national_laws,
        search_state_laws,
        calculate_challan,
        resolve_location,
        search_web_fallback
    ]
    
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT
    )
    
    return agent

# Singleton instance
try:
    agent_executor = get_agent_executor()
except ValueError as e:
    print(f"Warning: {e}")
    agent_executor = None
