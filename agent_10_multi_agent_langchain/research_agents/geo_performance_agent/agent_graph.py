from typing import Dict, List, Optional, TypedDict, Any
from datetime import datetime
import pandas as pd
from langgraph.graph import Graph, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command
from google.cloud import bigquery
from dotenv import load_dotenv
import json
import requests
import base64
import pytz
import urllib.parse
import numpy as np
from fpdf import FPDF
import os
from google.adk.tools.function_tool import FunctionTool

load_dotenv()

class BudgetOptState(TypedDict):
    chat_history: List[dict]
    user_input: str
    merged_data: List[dict]
    recommendations: List[str]
    requirements: dict
    explanation: str

def get_ads_cost_data(state: BudgetOptState, dataset_id: str):
    print("▶️ get_ads_data()")
    try:
        dataset_id = dataset_id
        start_date = state['requirements']['start_date']
        end_date = state['requirements']['end_date']

        query = f"""
        SELECT 
            report_date,
            region,
            SUM(cost) as cost
        FROM (
            SELECT report_date, region, SUM(cost_source) as cost 
            FROM `{dataset_id}.export_ad_geo_data` 
            GROUP BY report_date, region
        )
        WHERE report_date BETWEEN DATE(@start_date) AND DATE(@end_date) 
        GROUP BY report_date, region  
        ORDER BY report_date, region
        """

        query_params = [
            bigquery.ScalarQueryParameter("dataset_id", "STRING", start_date),
            bigquery.ScalarQueryParameter("start_date", "STRING", start_date),
            bigquery.ScalarQueryParameter("end_date", "STRING", end_date)
        ]

        client = bigquery.Client()
        job_config = bigquery.QueryJobConfig(query_parameters=query_params)
        ads_cost_df = client.query(query, job_config=job_config).to_dataframe()
    
        print(ads_cost_df)
        return ads_cost_df
    except Exception as e:
        error_msg = f"❌ Error fetching ads data: {str(e)}"
        state['chat_history'].append({"role": "assistant", "content": error_msg})
        state['error'] = error_msg
        return state
    
def get_ads_revenue_data(state: BudgetOptState, project_id: str, username: str, secret: str):
    print(state)
    print("▶️ get_ads_revenue_data()")
    # Define your variables
    str_project_timezone = 'Australia/Sydney'
    event_name = 'Order Received'
    event_property = 'cart_total_amount'

    try:
        start_date_str = state['requirements']['start_date']
        end_date_str = state['requirements']['end_date']        
        # Get the original date from the adjusted date
        project_timezone = pytz.timezone(str_project_timezone)  # Already defined in your project
        # Parse the adjusted date
        adjusted_start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=project_timezone)
        adjusted_end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=project_timezone)

        # Convert to UTC to reverse the offset
        original_start_date_utc = adjusted_start_date.astimezone(pytz.utc)
        # Remove the timezone info to get the original date
        original_start_date = original_start_date_utc.replace(tzinfo=None)
        # Convert to UTC to reverse the offset
        original_end_date_utc = adjusted_end_date.astimezone(pytz.utc)
        # Remove the timezone info to get the original date
        original_end_date = original_end_date_utc.replace(tzinfo=None)


        start_date_str = original_start_date.strftime("%Y-%m-%d")
        end_date_str = original_end_date.strftime("%Y-%m-%d")

        # Encode the authorization
        auth_header = base64.b64encode(f"{username}:{secret}".encode('ascii')).decode('ascii')

        # Define the URL and payload for the JQL request
        event_json = json.dumps([event_name])
        event_param = urllib.parse.quote(event_json)
        url = (
            f"https://data-eu.mixpanel.com/api/2.0/export?"
            f"project_id={project_id}&from_date={start_date_str}&to_date={end_date_str}"
            f"&event={event_param}"
        )

        # Set headers with authorization
        headers = {
            "accept": "text/plain",
            "authorization": f"Basic {auth_header}"
        }

        # Make the POST request
        response = requests.get(url, headers=headers)
        
        # Parse the JSON response if the request is successful
        if response.status_code == 200:

            response_data = response.text
            json_data = [json.loads(line) for line in response_data.splitlines()]


            # Extract relevant fields
            for entry in json_data:

                if not isinstance(entry.get('properties'), list):
                    
                    entry['properties'] = [entry['properties']]  # Wrap it in a list if it's a single dictionary

            # Now proceed with json_normalize

            mixpanel_export_dict = pd.json_normalize(json_data, 'properties', ['event'], errors='ignore')
            mixpanel_export_df = pd.DataFrame(mixpanel_export_dict)
            print(mixpanel_export_df)
            mixpanel_export_df['report_date'] =mixpanel_export_df['report_date'] = (
                                                    pd.to_datetime(mixpanel_export_df['time'], unit='s', utc=True)
                                                    .dt.tz_convert('Australia/Sydney')
                                                    .dt.strftime("%Y-%m-%d")
                                                )

            # Aggregate by report_date and region, summing event_property
            ads_revenue_df = (
                mixpanel_export_df
                .groupby(['report_date', '$region'], as_index=False)
                .agg({event_property: 'sum'})
            )
            ads_revenue_df.rename(columns={event_property: 'revenue'}, inplace=True)
            ads_revenue_df.rename(columns={'$region': 'region'}, inplace=True)
            #ads_revenue_df['region'] = ads_revenue_df['region'].replace('New South Wales', 'Alabama')

            return ads_revenue_df

        else:
            print("Error:", response.status_code, response.text)
            return None
       
    except Exception as e:
        error_msg = f"❌ Error fetching revenue data: {str(e)}"
        print(error_msg)
        #state['error'] = error_msg
        return state
    
def merge_ads_cost_and_revenue(ads_cost_df: pd.DataFrame, ads_revenue_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge ads cost and revenue DataFrames by report_date and region.
    Returns a DataFrame with columns for costs, revenue, and their sums.
    """
    print("▶️ merge_ads_cost_and_revenue()")
    ads_cost_df['report_date'] = ads_cost_df['report_date'].astype(str)
    ads_revenue_df['report_date'] = ads_revenue_df['report_date'].astype(str)
    ads_cost_df['region'] = ads_cost_df['region'].astype(str)
    ads_revenue_df['region'] = ads_revenue_df['region'].astype(str)
    merged_df = pd.merge(
        ads_cost_df,
        ads_revenue_df,
        on=['report_date', 'region'],
        how='left',  # Use 'outer' to keep all dates/regions, or 'inner' for only matches
        suffixes=('_cost', '_revenue')
    )

    # Group by region and sum all numeric columns
    merged_df = (
        merged_df
        .groupby('region', as_index=False)
        .sum(numeric_only=True)
    )
    merged_df['roas'] = merged_df['revenue'] / merged_df['cost']
    merged_df['roas'] = merged_df['roas'].fillna(0)
    print(merged_df)
    return merged_df


def identify_top_bottom_regions(merged_df: pd.DataFrame):
    """
    Split regions into above- and below-average ROAS groups.
    """
    print("▶️ identify_top_bottom_regions()")

    average_roas = merged_df['roas'].mean()
    top_regions = merged_df[merged_df['roas'] > average_roas].copy()
    bottom_regions = merged_df[merged_df['roas'] < average_roas].copy()
    return top_regions, bottom_regions, average_roas

def calculate_budget_reallocation(merged_df: pd.DataFrame, reallocation_fraction: float = 0.2) -> pd.DataFrame:
    """
    Suggest budget reallocations: move fraction of cost from low-ROAS to high-ROAS regions.
    """
    print("▶️ calculate_budget_reallocation()")
    top_regions, bottom_regions, average_roas = identify_top_bottom_regions(merged_df)

    merged_df['budget_change'] = 0.0

    # Step 1: calculate reduction in low-ROAS regions
    for idx, row in merged_df.iterrows():
        if row['roas'] < average_roas:
            merged_df.at[idx, 'budget_change'] = -row['cost'] * reallocation_fraction

    # Step 2: distribute freed-up budmerged_dfget to high-ROAS regions
    total_funds_to_redistribute = -merged_df[merged_df['budget_change'] < 0]['budget_change'].sum()
    top_regions_total_cost = top_regions['cost'].sum()

    for idx, row in merged_df.iterrows():
        if row['roas'] > average_roas:
            share = row['cost'] / top_regions_total_cost
            merged_df.at[idx, 'budget_change'] = share * total_funds_to_redistribute

    return merged_df

def calculate_advanced_budget_reallocation(merged_df: pd.DataFrame, 
                                            reallocation_fraction: float = 0.2,
                                            min_spend: float = 0,
                                            max_uplift_pct: float = 0.5) -> pd.DataFrame:
    """
    Advanced reallocation: uses ROAS percentiles, marginal gain, and budget caps.
    """
    print("▶️ advanced_budget_reallocation()")
    p25 = merged_df['roas'].quantile(0.25)
    p75 = merged_df['roas'].quantile(0.75)
    average_roas = merged_df['roas'].mean()

    merged_df['tier'] = 'middle'
    merged_df.loc[(merged_df['roas'] <= p25) | (merged_df['roas'] == 0), 'tier'] = 'bottom'
    merged_df.loc[(merged_df['roas'] >= p75) & (merged_df['roas'] > 0), 'tier'] = 'top'
    merged_df['marginal_gain'] = merged_df['roas'] - average_roas
    merged_df['budget_change'] = 0.0
    

    # Reduce from bottom
    for idx, row in merged_df.iterrows():
        if row['tier'] == 'bottom':
            merged_df.at[idx, 'budget_change'] = -row['cost'] * reallocation_fraction
            print(merged_df.at[idx, 'budget_change'])
    print(merged_df)
    total_funds_to_redistribute = -merged_df[merged_df['budget_change'] < 0]['budget_change'].sum()
    print(total_funds_to_redistribute)
    total_marginal_gain = merged_df.loc[merged_df['tier'] == 'top', 'marginal_gain'].sum()
    print(total_marginal_gain)

    # Allocate to top by marginal gain
    for idx, row in merged_df.iterrows():
        if row['tier'] == 'top' and total_marginal_gain > 0:
            share = row['marginal_gain'] / total_marginal_gain
            merged_df.at[idx, 'budget_change'] = share * total_funds_to_redistribute

    # Step 3: Calculate new budgets, apply min floor and max uplift cap
    merged_df['new_budget'] = merged_df['cost'] + merged_df['budget_change']
    merged_df['new_budget'] = merged_df['new_budget'].clip(lower=min_spend)
    merged_df['budget_change'] = merged_df['new_budget'] - merged_df['cost']
    merged_df['budget_change'] = np.minimum(merged_df['budget_change'], merged_df['cost'] * max_uplift_pct)
    
    return merged_df

def generate_reallocation_recommendations(merged_df: pd.DataFrame) -> List[str]:
    """
    Generate human-readable recommendations.
    """
    print("▶️ generate_reallocation_recommendations()")
    recommendations = []
    for idx, row in merged_df.iterrows():
        if row['budget_change'] < 0:
            recommendations.append(
                f"⬇ Reduce budget in {row['region']} by ${-row['budget_change']:.2f} (ROAS: {row['roas']:.2f})"
            )
        elif row['budget_change'] > 0:
            recommendations.append(
                f"⬆ Increase budget in {row['region']} by ${row['budget_change']:.2f} (ROAS: {row['roas']:.2f})"
            )
        else:
            recommendations.append(
                f"⏸ No change for {row['region']} (ROAS: {row['roas']:.2f})"
            )
    return recommendations

def get_data(state: BudgetOptState):
    from .firebase_client import get_connection, get_organization

    print("▶️ get_data()")
        # Stage 1: Fetch ads cost data
    print(state)

    connection_info = get_connection(state['requirements']['connection_id'])
    dataset_id = connection_info.get('dataset_id')
    print(dataset_id)
    organization_info = get_organization(connection_info.get('organization_id'))
    destination_info = organization_info.get('apps', {}).get(connection_info.get('destination_id'))
    project_id = destination_info.get('project_id')
    secret = destination_info.get('service_account_secret')
    username = destination_info.get('service_account_user_name')
    print(dataset_id, project_id, secret, username)

    state["chat_history"].append({"role": "system", "content": "🔄 Fetching ads cost data..."})
    ads_cost_df = get_ads_cost_data(state, dataset_id)
    
    # Stage 2: Fetch ads revenue data
    state["chat_history"].append({"role": "system", "content": "🔄 Fetching ads revenue data..."})
    ads_revenue_df = get_ads_revenue_data(state, project_id, username, secret)
    
    # Stage 3: Merge cost and revenue data
    state["chat_history"].append({"role": "system", "content": "🔄 Merging cost and revenue data..."})
    merged_df = merge_ads_cost_and_revenue(ads_cost_df, ads_revenue_df)
    
    # Stage 4: Save merged data
    state["chat_history"].append({"role": "system", "content": "✅ Data merge complete."})
    state['merged_data'] = merged_df.to_dict(orient='records')
    return state

def get_budget_optimisation_recommendations(state: BudgetOptState):
    print("▶️ get_budget_optimisation_recommendations()")
    # Stage 1: Load merged data
    state["chat_history"].append({"role": "system", "content": "🔄 Loading merged cost and revenue data..."})
    merged_df = pd.DataFrame(state['merged_data'])

    # Stage 2: Calculate advanced budget reallocation
    state["chat_history"].append({"role": "system", "content": "🔄 Calculating advanced budget reallocation..."})
    merged_df = calculate_advanced_budget_reallocation(merged_df)
    state['merged_data'] = merged_df.to_dict(orient='records')

    # Stage 3: Generate recommendations
    state["chat_history"].append({"role": "system", "content": "🔄 Generating reallocation recommendations..."})
    recommendations = generate_reallocation_recommendations(merged_df)
    print(recommendations)
    state["recommendations"] = recommendations
    # Stage 4: Add recommendations to chat history
    for rec in recommendations:
        state["chat_history"].append({"role": "assistant", "content": rec})
    
    # Optionally, mark completion
    state["chat_history"].append({"role": "system", "content": "✅ Budget optimisation recommendations complete."})

    return state


def explain_recommendations(state: BudgetOptState) -> Dict[str, Any]:
    print("▶️ explain_recommendations()")
    try:
        from .sub_agents.explanation_agent import explain_recommendations_agent

        state = explain_recommendations_agent(state)
        return state
    except Exception as e:
        state['error'] = str(e)
        return state

def create_geo_performance_optimization_graph(checkpointer=None) -> Graph:
    print("▶️ create_geo_performance_optimization_graph()")
    if checkpointer is None:
        checkpointer = InMemorySaver()
    workflow = StateGraph(BudgetOptState)

    workflow.add_node("get_data", get_data)
    workflow.add_node("get_budget_optimisation_recommendations", get_budget_optimisation_recommendations)
    workflow.add_node("explain_recommendations", explain_recommendations)
    workflow.set_entry_point("get_data")

    workflow.add_edge("get_data", "get_budget_optimisation_recommendations")
    workflow.add_edge("get_budget_optimisation_recommendations", "explain_recommendations")
    return workflow.compile(checkpointer=checkpointer)



import tempfile

def generate_pdf(content: str) -> str:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in content.split("\n"):
        pdf.multi_cell(0, 10, line)
    
    # Save to temp file
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(temp_pdf.name)
    return temp_pdf.name

def start_geo_performance_optimization(start_date: str, end_date: str) -> Dict:
    print("▶️ start_geo_performance_optimization()")
    print(start_date, end_date)
    user_input= "hello"
    checkpointer=None
    graph = create_geo_performance_optimization_graph(checkpointer)
    thread_config = {"configurable": {"thread_id": "some_id"}}
    requirements = {
        'start_date': start_date, 'end_date': end_date, 'connection_id': 's00IGNsLa6zdswBy1A7X_google_ads_1e2641405_mixpanel_6c88ab89d_53127b64'
    }
    initial_state = {
        "user_input": user_input,
        "chat_history": [{"role": "user", "content": user_input}],
        "requirements": requirements
    }
    
    result_state = graph.invoke(initial_state, config=thread_config)

    
    return result_state


# Wrap your LangGraph entrypoint function
geo_performance_optimization_tool = FunctionTool(start_geo_performance_optimization)

if __name__ == "__main__":
    graph = create_geo_performance_optimization_graph()
    thread_config = {"configurable": {"thread_id": "some_id"}}
    
    state = {
            "chat_history": [{"role": "user", "content": "Start optimization"}],
            "user_input": "Start optimization",
            "requirements": {'start_date': '2025-04-01', 'end_date': '2025-04-30', 'connection_id': 's00IGNsLa6zdswBy1A7X_google_ads_1e2641405_mixpanel_6c88ab89d_53127b64'},
        }
    result_state = graph.invoke(state, config=thread_config)
    print(result_state)

    #get_ads_revenue_data(BudgetOptState())
    