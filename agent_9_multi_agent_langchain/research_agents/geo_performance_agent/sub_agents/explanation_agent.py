# Define the explanation prompt
EXPLANATION_PROMPT = """
You are a marketing analyst assistant.

Here is a list of budget reallocation recommendations:

{recommendations}

Please write a clear, concise, and persuasive explanation for a business audience covering:
- Which regions are getting more budget and why
- Which regions are getting less budget and why
- The overall strategy behind these changes
- What business outcome we hope to achieve

Respond only with valid string in this format:

    "Your natural language explanation here."


Rules:
- Do NOT output anything outside the JSON block.
- Keep the explanation short, clear, and non-technical.
"""

from typing import Dict, List, Optional, TypedDict, Union
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, Graph
from langchain.chains.llm import LLMChain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_vertexai import ChatVertexAI

# Build the prompt template
explanation_agent_llm_prompt = ChatPromptTemplate.from_template(EXPLANATION_PROMPT)

# Create the LLMChain
explanation_agent_chain = LLMChain(
    llm=ChatVertexAI(model="gemini-1.5-flash"),
    prompt=explanation_agent_llm_prompt,
    output_key="explanation"
)

def explain_recommendations_agent(state: dict):
    print("⚡ inside explain_recommendations_agent")
    
    chat_history = state.get("chat_history", [])
    recommendations = state.get("recommendations",[])
    # Run the chain
    result = explanation_agent_chain.invoke({
            "chat_history": chat_history,
            "recommendations": recommendations,
    })
    print(result)
    state["chat_history"].append({"role": "assistant", "content": result["explanation"]})
    state["explanation"] = result["explanation"]
        
    return state
 