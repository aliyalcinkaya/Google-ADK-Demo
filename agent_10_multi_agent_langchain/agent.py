import datetime
from zoneinfo import ZoneInfo
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools import google_search  # Import the tool
from typing import Union, List, Optional, Iterable
import os
import json
import requests
import gzip
from fpdf import FPDF
import io

# ────────────────────────────────────────────────────────────────────────────
# 1. Tools
# ────────────────────────────────────────────────────────────────────────────
# moved Mixpanel tool to its own file
from .mixpanel_tools import query_mixpanel
from .bigquery_tools import query_bigquery
from .research_agents.geo_performance_agent.agent_graph import geo_performance_optimization_tool  
import google.genai.types as types

from google.adk.agents.callback_context import CallbackContext # Or ToolContext
from google.adk.tools import FunctionTool
#moved prompts to a separate file
from .prompts import (
    GET_MIXPANEL_QUERY_AGENT_INSTRUCTION,
    MIXPANEL_QUERY_RUNNER_AGENT_INSTRUCTION,
    QUERY_AGENT_INSTRUCTION,
    DATA_PLANNER_AGENT_INSTRUCTION,
    ROOT_AGENT_INSTRUCTION,
    GOOGLE_SEARCH_AGENT_INSTRUCTION,
    GEO_PERFORMANCE_AGENT_INSTRUCTION,  
    BIGQUERY_QUERY_RUNNER_AGENT_INSTRUCTION,
    GET_BIGQUERY_QUERY_AGENT_INSTRUCTION,
)

# ────────────────────────────────────────────────────────────────────────────
# 2. Sub-agents (optional - each can focus on a single sub-task)
# ────────────────────────────────────────────────────────────────────────────
def save_generated_report(explanation: str,tool_context=None):
    """Saves generated PDF report bytes as an artifact."""
    context: CallbackContext = tool_context
    
    def generate_pdf_bytes(explanation: str) -> bytes:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        for line in explanation.split("\n"):
            pdf.multi_cell(0, 10, line)
        # ✅ return PDF as bytes
        return pdf.output(dest="S").encode("latin-1")

    pdf_bytes = generate_pdf_bytes(explanation)
    print(explanation)
    report_artifact =types.Part(
    inline_data=types.Blob(
        mime_type="application/pdf",
        data=pdf_bytes
    )
)
    filename = "generated_report.pdf"

    try:
        version = context.save_artifact(filename=filename, artifact=report_artifact)
        print(f"Successfully saved artifact '{filename}' as version {version}.")
        return {"filename": filename}
    except ValueError as e:
        print(f"Error saving artifact: {e}. Is ArtifactService configured?")
        return {"error": str(e)}
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {"error": str(e)}
save_generated_report_tool = FunctionTool(
    save_generated_report
)

geo_performance_agent = Agent(
    name="geo_performance_agent",
    model="gemini-2.0-flash",
    description="Hands off to agent that runs the geo performance optimization graph.",
    instruction=GEO_PERFORMANCE_AGENT_INSTRUCTION,
    tools=[geo_performance_optimization_tool, save_generated_report_tool],
    output_key="geo_performance_recommendations"  

)

# this is the agent that runs the query and returns the raw rows.
mixpanel_query_runner_agent = Agent(
    name="mixpanel_query_runner_agent",
    model="gemini-2.0-flash",
    description="Builds & executes the Mixpanel query, returns raw rows.",
    instruction=MIXPANEL_QUERY_RUNNER_AGENT_INSTRUCTION,
    tools=[query_mixpanel],

)
# this is the agent that selects the correct Mixpanel events based on the user's goal.
# To do: replace this with an agent that can do this for BQ
get_mixpanel_query_agent = Agent(
    name="get_mixpanel_query",
    model="gemini-2.0-flash",
    description="Chooses the correct Mixpanel events based on the user's goal.",
    instruction=GET_MIXPANEL_QUERY_AGENT_INSTRUCTION,
    tools=[AgentTool(agent=mixpanel_query_runner_agent)],
)

bigquery_query_runner_agent = Agent(
    name="bigquery_query_runner_agent",
    model="gemini-2.0-flash",
    description="Builds & executes the BigQuery query, returns raw rows.",
    instruction=BIGQUERY_QUERY_RUNNER_AGENT_INSTRUCTION,
    tools=[query_bigquery],
    output_key="bigquery_data"
)



get_bigquery_query_agent = Agent(
    name="get_bigquery_query",
    model="gemini-2.0-flash",
    description="Returns the BigQuery SQL query to use with bigquery_query_runner_agent which queries the table.",
    instruction=GET_BIGQUERY_QUERY_AGENT_INSTRUCTION,
    tools=[AgentTool(agent=bigquery_query_runner_agent)],
    output_key="bigquery_query"
)


# researcher agent understand the clients research request, selects the research agent tool 
# and plans the parameters of the research 
query_agent = Agent(
    name="query_agent",
    model="gemini-2.0-flash",
    description="Plans the parameters of the research",
    instruction=QUERY_AGENT_INSTRUCTION,
    sub_agents=[
        get_mixpanel_query_agent,
        get_bigquery_query_agent
    ]
)

# data planner agent
data_planner = Agent(
    name="data_planner",
    model="gemini-2.0-flash",
    description="Creates tracking requirements for new events based on customer requests",
    instruction=DATA_PLANNER_AGENT_INSTRUCTION
)

# google search agent
google_search = Agent(
    model='gemini-2.0-flash-exp',
    name='google_search',
    instruction=GOOGLE_SEARCH_AGENT_INSTRUCTION,
    tools=[google_search]
)

# ────────────────────────────────────────────────────────────────────────────
# 3. Root orchestration agent
# ────────────────────────────────────────────────────────────────────────────

root_agent = Agent(
    name="agent_router",
    model="gemini-2.0-flash",
    description="Job is to route the user's request to the right sub-agent.",
    instruction=ROOT_AGENT_INSTRUCTION,
    sub_agents=[
        query_agent,
        geo_performance_agent,
    ],
    tools=[
        AgentTool(agent=google_search), 
        AgentTool(agent=data_planner),
    ]
)


