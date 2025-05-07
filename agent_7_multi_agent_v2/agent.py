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


#moved prompts to a separate file
from .prompts import (
    SELECT_EVENT_AGENT_INSTRUCTION,
    QUERY_RUNNER_AGENT_INSTRUCTION,
    RESEARCHER_AGENT_INSTRUCTION,
    DATA_PLANNER_AGENT_INSTRUCTION,
    ROOT_AGENT_INSTRUCTION,
    GOOGLE_SEARCH_AGENT_INSTRUCTION,
)


# ────────────────────────────────────────────────────────────────────────────
# 1. Tools
# ────────────────────────────────────────────────────────────────────────────
# moved Mixpanel tool to its own file
from .mixpanel_tools import query_mixpanel

# from .marketing effectiveness import xxx

# ────────────────────────────────────────────────────────────────────────────
# 2. Sub-agents (optional - each can focus on a single sub-task)
# ────────────────────────────────────────────────────────────────────────────

marketing_effectiveness_agent = Agent(
    name="marketing_effectiveness_agent",
    model="gemini-2.0-flash",
    description="Chooses the correct Mixpanel events based on the user's goal.",
    instruction=SELECT_EVENT_AGENT_INSTRUCTION
)



# this is the agent that selects the correct Mixpanel events based on the user's goal.
# To do: replace this with an agent that can do this for BQ
select_event_agent = Agent(
    name="select_event",
    model="gemini-2.0-flash",
    description="Chooses the correct Mixpanel events based on the user's goal.",
    instruction=SELECT_EVENT_AGENT_INSTRUCTION
)

# this is the agent that runs the query and returns the raw rows.
query_runner_agent = Agent(
    name="query_runner",
    model="gemini-2.0-flash",
    description="Builds & executes the Mixpanel query, returns raw rows.",
    instruction=QUERY_RUNNER_AGENT_INSTRUCTION,
    tools=[query_mixpanel],
    output_key="mixpanel_rows",
)

# researcher agent understand the clients research request, selects the research agent tool 
# and plans the parameters of the research 
researcher = Agent(
    name="researcher",
    model="gemini-2.0-flash",
    description="Plans the parameters of the research",
    instruction=RESEARCHER_AGENT_INSTRUCTION,
    tools=[
        AgentTool(agent=select_event_agent),
        AgentTool(agent=query_runner_agent)
    ]
)

# this is a demo agent to test highlevel routing capabilities.
data_planner = Agent(
    name="data_planner",
    model="gemini-2.0-flash",
    description="Creates tracking requirements for new events based on customer requests",
    instruction=DATA_PLANNER_AGENT_INSTRUCTION
)

# this is a demo agent to test highlevel routing capabilities.
google_search = Agent(
    model='gemini-2.0-flash-exp',
    name='SearchAgent',
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
    tools=[
        AgentTool(agent=google_search), 
        AgentTool(agent=researcher),
        AgentTool(agent=data_planner),
    ]
)
