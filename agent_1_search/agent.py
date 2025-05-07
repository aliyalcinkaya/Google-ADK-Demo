from google.adk.agents import Agent
from google.adk.tools import google_search  # Import the tool


root_agent = Agent(
   name="agent_2",    # A unique name for the agent.
   model="gemini-2.0-flash-exp",   # The Large Language Model (LLM) that agent will use.
   #model="gemini-2.0-flash-live-preview-04-09" # Vertex AI Studio
   description="Agent to answer questions using Google Search.",  # A short description of the agent's purpose.
   instruction="You are an expert researcher. You always stick to the facts.",    # Instructions to set the agent's behavior.
   tools=[google_search]   # Add google_search tool to perform grounding with Google search.
)