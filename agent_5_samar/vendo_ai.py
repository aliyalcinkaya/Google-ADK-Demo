import os
import asyncio
import json
import streamlit as st
from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.adk.tools import FunctionTool
from google.genai import types
from dotenv import load_dotenv
import google.generativeai as genai
import time
from datetime import datetime
import nest_asyncio
import pandas as pd
import random

# Apply nest_asyncio to fix event loop issues
nest_asyncio.apply()

# Load environment variables
load_dotenv()

# Suppress warnings
import warnings
warnings.filterwarnings("ignore")

# Configure logging
import logging
logging.basicConfig(level=logging.ERROR)

# Constants
MODEL_GEMINI_1_5_FLASH = "gemini-1.5-flash"
MODEL_GEMINI_1_5_PRO = "gemini-1.5-pro"

# Initialize Gemini
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    st.error("GOOGLE_API_KEY environment variable not found in .env file")
    st.stop()

genai.configure(api_key=api_key)

# Initialize session state
def initialize_session():
    if 'conversation' not in st.session_state:
        st.session_state.conversation = []
        st.session_state.workflow_tasks = {}
        st.session_state.current_workflow_id = None
        st.session_state.phase = "requirements"
        st.session_state.session_service = InMemorySessionService()
        st.session_state.session_id = f"session_{int(time.time())}"
        st.session_state.session_service.create_session(
            app_name="business_chatbot",
            user_id="user1",
            session_id=st.session_state.session_id
        )
        st.session_state.business_requirements = None
        st.session_state.selected_analyses = []
        st.session_state.current_recommendations = []
        st.session_state.current_data_analysis = {}
        st.session_state.analysis_options = [
            {"emoji": "📢", "name": "Marketing Campaigns", "key": "marketing"},
            {"emoji": "🌍", "name": "Locations; Cities, Regions", "key": "locations"},
            {"emoji": "📦", "name": "Products: which products to promote", "key": "products"},
            {"emoji": "💰", "name": "Pricing and Promotions", "key": "pricing"}
        ]

# Business Requirements Functions
def create_business_summary(strategic_focus: str, specific_goals: str, constraints: str) -> dict:
    """Creates a structured JSON summary of business requirements."""
    summary = {
        "business_requirements": {
            "strategic_focus": strategic_focus,
            "specific_goals": specific_goals,
            "constraints": constraints,
        },
        "metadata": {
            "version": "1.0",
            "timestamp": datetime.now().isoformat()
        }
    }
    
    workflow_id = f"workflow_{len(st.session_state.workflow_tasks) + 1}"
    st.session_state.current_workflow_id = workflow_id
    st.session_state.workflow_tasks[workflow_id] = {
        "business_requirements": summary,
        "status": "requirements_complete"
    }
    st.session_state.phase = "research"
    st.session_state.business_requirements = summary
    
    return summary

# Dynamic Analysis Functions
def run_analysis(analysis_name: str, business_requirements: dict) -> dict:
    """Executes a specific analysis and returns dynamic results."""
    if not business_requirements:
        return {"error": "Business requirements not found"}
    
    reqs = business_requirements.get("business_requirements", {})
    
    # Generate dynamic data based on analysis type
    if analysis_name == "Marketing Campaigns":
        campaigns = ["Meta Ads", "Google Ads", "Influencer", "Email", "Affiliate"]
        data = []
        for campaign in campaigns:
            spend = random.randint(5000, 50000)
            conversions = random.randint(50, 500)
            revenue = spend * random.uniform(1.2, 3.5)
            roi = revenue / spend
            data.append({
                "campaign": campaign,
                "spend": f"${spend:,}",
                "conversions": conversions,
                "revenue": f"${revenue:,.0f}",
                "roi": f"{roi:.1f}x",
                "status": "High Potential" if roi > 2 else "Moderate"
            })
        
        opportunities = [
            {
                "title": "Increase Meta Ads Campaign for Regional Australia",
                "description": "Lower cost per acquisition and high LTV observed in last 3 months",
                "recommendation": "Increase budget by up to 50% without reducing profit margins below 10%",
                "data_source": "Meta Ads data (17 Jan 2025 to 17 April 2025)"
            },
            {
                "title": "Increase budget for Top Products in Google Shopping",
                "description": "Strong performance in shopping campaigns with ROI above 3x",
                "recommendation": "Reallocate 30% of budget from underperforming campaigns",
                "data_source": "Google Ads performance reports"
            }
        ]
        
        return {
            "analysis": "marketing_campaigns",
            "data": data,
            "opportunities": opportunities,
            "methodology": "Analyzed performance metrics including CPA, LTV, and profit margins"
        }
    
    elif analysis_name == "Locations; Cities, Regions":
        regions = ["North America", "Europe", "Asia", "Australia", "South America"]
        data = []
        for region in regions:
            revenue = random.randint(20000, 100000)
            growth = random.uniform(0.5, 15.0)
            margin = random.uniform(10.0, 25.0)
            data.append({
                "region": region,
                "revenue": f"${revenue:,}",
                "growth": f"{growth:.1f}%",
                "margin": f"{margin:.1f}%",
                "trend": "↑" if growth > 5 else "↓"
            })
        
        return {
            "analysis": "locations",
            "data": data,
            "opportunities": [
                {
                    "title": "Expand in Asia Pacific region",
                    "description": "Highest growth rate with good margins observed",
                    "recommendation": "Allocate 20% more budget to APAC marketing",
                    "data_source": "Regional sales data Q1 2025"
                }
            ],
            "methodology": "Analyzed regional sales data and growth trends"
        }
    
    # Similar dynamic generation for other analysis types
    else:
        return {
            "analysis": analysis_name,
            "data": [],
            "opportunities": [],
            "methodology": "Standard performance analysis"
        }

# UI Display Functions
def display_initial_options():
    """Displays the initial analysis options as text."""
    st.session_state.current_data_analysis = {}  # Reset current analysis
    
    st.markdown("""
    Here are some of the things that I can look at to help you increase your profits. 
    Let me know which ones you want me to look into:
    """)
    
    # Display options as text with emojis
    for option in st.session_state.analysis_options:
        st.markdown(f"- {option['emoji']} {option['name']}")
    
    st.markdown("\nYou can say 'look into all' or specify which ones (e.g. 'Marketing and Locations')")

def process_user_selection(user_input: str):
    """Processes user text input to determine which analyses to run."""
    user_input = user_input.lower()
    
    # Check for "all" command
    if "all" in user_input:
        return [option["name"] for option in st.session_state.analysis_options]
    
    # Check for specific analyses
    selected = []
    for option in st.session_state.analysis_options:
        if option["name"].lower() in user_input:
            selected.append(option["name"])
    
    return selected

# Initialize Agents
def initialize_agents():
    """Initialize all agents with their tools and instructions."""
    # Business Requirements Agent
    business_agent = Agent(
        name="business_advisor",
        model=MODEL_GEMINI_1_5_PRO,
        description="Gathers business requirements from the user",
        instruction="""You are a professional business advisor gathering information from the user.
        
        Ask these questions ONE AT A TIME in order:
        1. "What is your focus metric? I.e is it profit or revenue growth? In the future we'll bring this automatically, through the business model context"
        2. "Do you have a specific goal in mind (e.g., +$50K/month)?"
        3. "Are there any research constraints we should keep in mind for our analysis?"
        
        After all answers:
        1. Provide a comprehensive summary
        2. Call create_business_summary with their answers
        """,
        tools=[FunctionTool(create_business_summary)]
    )
    
    # Research Agent
    research_agent = Agent(
        name="research_agent",
        model=MODEL_GEMINI_1_5_PRO,
        description="Proposes and runs research analyses",
        instruction="""You run research analyses based on business requirements.
        
        When you receive an analysis request:
        1. Call run_analysis with:
           - analysis_name: the name of the analysis
           - business_requirements: the provided requirements
        2. Present the findings and recommendations
        """,
        tools=[FunctionTool(run_analysis)]
    )
    
    return business_agent, research_agent

async def get_agent_response(runner, prompt):
    """Async function to get agent response."""
    content = types.Content(role='user', parts=[types.Part(text=prompt)])
    response = ""
    
    try:
        async for event in runner.run_async(
            user_id="user1",
            session_id=st.session_state.session_id,
            new_message=content
        ):
            if event.is_final_response() and event.content and event.content.parts:
                response = event.content.parts[0].text
                break
    except Exception as e:
        response = f"Error generating response: {str(e)}"
    
    return response

# Main application
def main():
    initialize_session()
    global business_agent, research_agent
    business_agent, research_agent = initialize_agents()
    
    st.title("Vendo Marketing AI Assistant")
    
    # Display conversation history
    for msg in st.session_state.conversation:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    
    # Handle different phases
    if st.session_state.phase == "requirements":
        # User input
        if prompt := st.chat_input("How can I help optimize your business profits?"):
            st.session_state.conversation.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)
            
            # Create runner
            runner = Runner(
                agent=business_agent,
                app_name="business_chatbot",
                session_service=st.session_state.session_service
            )
            
            # Get response
            with st.spinner("Analyzing..."):
                response = asyncio.run(get_agent_response(runner, prompt))
            
            # Add to conversation
            st.session_state.conversation.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"):
                st.write(response)
    
    elif st.session_state.phase == "research":
        with st.chat_message("assistant"):
            display_initial_options()
        
        # User input for analysis selection
        if prompt := st.chat_input("Which analyses should I run?"):
            st.session_state.conversation.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)
            
            # Process user selection
            selected = process_user_selection(prompt)
            if selected:
                st.session_state.selected_analyses = selected
                st.session_state.phase = "running_analysis"
                st.rerun()
            else:
                st.warning("I didn't understand your selection. Please try again.")
    
    elif st.session_state.phase == "running_analysis":
        with st.chat_message("assistant"):
            if st.session_state.selected_analyses:
                # Run all selected analyses
                all_results = []
                for analysis_name in st.session_state.selected_analyses:
                    result = run_analysis(
                        analysis_name,
                        st.session_state.business_requirements
                    )
                    all_results.append(result)
                
                # Combine all results
                st.session_state.current_data_analysis = {
                    "analysis": "combined_analysis",
                    "data": [item for res in all_results for item in res.get('data', [])],
                    "opportunities": [opp for res in all_results for opp in res.get('opportunities', [])],
                    "methodology": "Combined analysis of all selected areas"
                }
                st.session_state.phase = "show_analysis"
                st.rerun()
    
    elif st.session_state.phase == "show_analysis":
        with st.chat_message("assistant"):
            analysis = st.session_state.current_data_analysis
            
            st.markdown("### Analysis Results:")
            
            # Show data table if available
            if analysis.get('data'):
                df = pd.DataFrame(analysis['data'])
                st.dataframe(df)
            
            st.markdown("---")
            st.markdown("### Opportunities Found:")
            
            for opp in analysis.get('opportunities', []):
                st.markdown(f"- **{opp['title']}**")
                st.markdown(f"  - {opp['description']}")
            
            st.markdown("---")
            st.markdown("Which opportunity would you like to explore further?")
            
            # Buttons for each opportunity
            for i, opp in enumerate(analysis.get('opportunities', [])):
                if st.button(f"Explore: {opp['title']}", key=f"opp_{i}"):
                    st.session_state.current_recommendations = [opp]
                    st.session_state.phase = "show_recommendation"
                    st.rerun()
    
    elif st.session_state.phase == "show_recommendation":
        with st.chat_message("assistant"):
            if not st.session_state.current_recommendations:
                st.session_state.phase = "research"
                st.rerun()
            
            rec = st.session_state.current_recommendations[0]
            analysis = st.session_state.current_data_analysis
            
            st.markdown(f"**Recommendation: {rec['title']}**")
            st.markdown(f"\n{rec['description']}\n")
            
            st.markdown("**Implementation Details:**")
            st.markdown(f"- {rec['recommendation']}")
            st.markdown(f"- Data Source: {rec['data_source']}")
            
            st.markdown("\nWould you like to implement this recommendation?")
            
            if st.button("Yes, implement this"):
                st.success("Recommendation implemented! We'll monitor results.")
                st.session_state.phase = "complete"
                st.rerun()
            
            if st.button("No, show other options"):
                st.session_state.phase = "show_analysis"
                st.rerun()
    
    elif st.session_state.phase == "complete":
        st.success("Analysis complete! Feel free to ask another question.")
        if st.button("Start New Analysis"):
            initialize_session()
            st.rerun()

if __name__ == "__main__":
    main()