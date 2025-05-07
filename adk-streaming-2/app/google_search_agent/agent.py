import datetime
from zoneinfo import ZoneInfo
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from typing import Union, List, Optional, Iterable
import os
import json
import requests
import gzip



# ────────────────────────────────────────────────────────────────────────────
# 1. Tools
# ────────────────────────────────────────────────────────────────────────────
def query_event(event_name: str) -> dict:
    if event_name == "Ad GEO Data":
        return {
            "status": "success",
            "report": (
                "Ad GEO Data = 1000"
            ),
        }
    else:
        return {
            "status": "error",
            "error_message": f" '{event_name}' is not available.",
        }


def query_mixpanel(
    from_date: str,
    to_date: str,
    event_names: Optional[List[str]] = None,
    where: Optional[str] = None,
    chunk_gzip: bool = True,
    timeout: int = 30,
) -> List[dict]:
    """
    Export data from Mixpanel within a specified date range and for specific events.

    Args:
        from_date (str): The start date for the data export.
        to_date (str): The end date for the data export.
        event_names (Optional[List[str]]): List of event names to filter the data.
        where (Optional[str]): Additional query conditions.
        chunk_gzip (bool): Whether to use gzip compression for chunks.
        timeout (int): Timeout for the request in seconds.

    Returns:
        List[dict]: A list of dictionaries containing the exported data.

    Raises:
        ValueError: If service-account credentials are missing.
        RuntimeError: If there is an error querying the Mixpanel API or processing data.
    """
    # Resolve credentials from parameters or environment variables
    user = (os.getenv("MIXPANEL_SERVICE_ACCOUNT_USERNAME"))    
    secret = (os.getenv("MIXPANEL_SERVICE_ACCOUNT_SECRET"))  
    if not (user and secret):
        raise ValueError(
            "Service-account credentials are missing. "
            "Pass them explicitly or set them in .env file as "
            "MIXPANEL_SERVICE_ACCOUNT_USERNAME and MIXPANEL_SERVICE_ACCOUNT_SECRET."
        )

    url = f"https://data-eu.mixpanel.com/api/2.0/export"  # us = "data", eu = "data-eu", in = "data-in"
    params = {
        "from_date": from_date,
        "to_date": to_date,
        "project_id": 3266709,   # REQUIRED for service-account auth
    }
    if event_names:
        params["event"] = json.dumps(event_names)
    if where:
        params["where"] = where

    headers = {"Accept-Encoding": "gzip"} if chunk_gzip else {}
    auth = (user, secret)          # HTTP Basic with service-account creds

    print(f"Querying Mixpanel for events from {from_date} to {to_date}")
    print("This might take a moment depending on the amount of data...")
    print("-" * 50)

    try:
        with requests.get(url, params=params, auth=auth,
                        headers=headers, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()

            raw_iter = (
                gzip.GzipFile(fileobj=resp.raw)
                if resp.headers.get("Content-Encoding") == "gzip"
                else resp.raw
            )
            events = [json.loads(line.decode("utf-8")) for line in raw_iter if line.strip()]

            # Count events by type
            event_count = {}
            total_count = 0

            for i, ev in enumerate(events):
                event_type = ev.get("event", "unknown")
                event_count[event_type] = event_count.get(event_type, 0) + 1
                total_count += 1

                # Print event details including all properties
                print(f"\nEvent #{i+1}: {event_type}")
                print("-" * 30)

                # Print all event properties in a readable format
                properties = ev.get('properties', {})
                if properties:
                    print("Properties:")
                    # Sort properties for better readability
                    for key, value in sorted(properties.items()):
                        # Format the value for better display
                        if isinstance(value, dict):
                            value_str = json.dumps(value, indent=2)
                            print(f"  {key}:")
                            for line in value_str.split('\n'):
                                print(f"    {line}")
                        else:
                            print(f"  {key}: {value}")
                else:
                    print("No properties found")

                # Just show a sample to avoid overwhelming output
                if i >= 9:  # Show only first 10 events with full properties
                    print(f"\n... (showing only first 10 events with full details)")
                    break

            print("\n" + "-" * 50)
            print(f"Total events found: {total_count}")
            print("Event Summary:")
            for event_type, count in event_count.items():
                print(f"- {event_type}: {count} events")

            return events

    except requests.RequestException as e:
        error_message = f"Error querying Mixpanel API: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_details = e.response.json()
                error_message += f" - Details: {json.dumps(error_details)}"
            except Exception:
                error_message += f" - Status code: {e.response.status_code}"
        raise RuntimeError(error_message)
    except Exception as e:
        raise RuntimeError(f"Error processing Mixpanel data: {str(e)}")




# ────────────────────────────────────────────────────────────────────────────
# 2. Sub-agents (optional - each can focus on a single sub-task)
# ────────────────────────────────────────────────────────────────────────────
select_event_agent = Agent(
    name="select_event",
    model="gemini-2.0-flash",
    description="Chooses the correct Mixpanel events based on the user's goal.",
    instruction=(
        """ 
        You are an analytics expert. Given the user's question. Findout the best event to query. Here are the events

        ### Event Name: Ad Geo Data
        Description: This event contains paid ads data from ad platforms at a campaign level, segmented by region. This event can be used to track ad spend, clicks, impressions, and conversion by region.
        Properties:
        - $ad_platform — Ad Platform
        - $insert_id — Insert ID
        - $region — Region
        - $source — Source
        - account_id — Advertising Account ID
        - account_name — Advertising Account Name
        - campaign_advertising_channel_type — Campaign Advertising Channel Type
        - campaign_id — Campaign ID
        - campaign_name — Campaign Name
        - clicks — Clicks
        - conversion_value — Conversion Value
        - conversions — Conversions
        - cost_reporting — Cost Reporting
        - cost_source — Cost Source
        - currency_reporting — Currency Reporting
        - currency_source — Currency Source
        - device_category — Device Category
        - impressions — Impressions
        - job_id — Job Id [Vendo]
        - utm_campaign — UTM Campaign
        - utm_content — UTM Content
        - utm_medium — UTM Medium
        - utm_source — UTM Source
        - utm_term — UTM Term
        - vendo_tracking_version — Vendo Tracking Version

        ### Event Name: Order Received
        Description: The order_received event is sent when a new order is created at Shopify. This order could be received from the online store or other sources. A received order does not mean an order is paid. An order may have multiple financial statuses. Use financial_status event property to see the orders' status. This event can be used to track revenue, profits, and gross profit
        Properties:
        - $insert_id — Insert ID
        - order_id — Order ID
        - shopify_order_id — Shopify Order ID
        - email — Email
        - currency — Currency
        - cart_subtotal_amount — Cart Subtotal Amount
        - total_discounts — Total Discounts
        - cart_total_amount — Cart Total Amount
        - tax_amount — Tax Amount
        - shipping_amount — Shipping Amount
        - billing_address — Billing Address
        - shipping_address — Shipping Address
        - confirmed — Confirmed
        - order_status_url — Order Status URL
        - payment_gateway — Payment Gateway
        - order_tags — Order Tags
        - processing_method — Processing Method
        - landing_page — Landing Page
        - financial_status — Financial Status
        - products — Products
        - app_id — App ID
        - app_name — App Name
        - test — Test
        - discount — Discount Codes
        - $source — Source
        - $import — Import
        - utm_source — UTM Source
        - utm_medium — UTM Medium
        - utm_campaign — UTM Campaign
        - utm_content — UTM Content
        - utm_term — UTM Term
        - event_type — Event Type
        - custom_order_attributes — Custom Order Attributes
        - payment_status — Payment Status
        - note — Order Note
        - vendo_tracking_version — Vendo Tracking Version
        - source_name — Source Name

        ### Event Name: Order Refunded
        Description: The order_refunded event logs when the order was fully refunded. Can be used to track refunds, refunds amount, and refunds by product.
        Properties:
        - $insert_id — Insert ID
        - order_id — Order ID
        - shopify_order_id — Shopify Order ID
        - customer_id — Customer ID
        - currency — Currency
        - confirmed — Confirmed
        - payment_gateway — Payment Gateway
        - products — Products
        - cart_subtotal_amount — Cart Subtotal Amount
        - cart_total_amount — Cart Total Amount
        - tax_amount — Tax Amount
        - total_discounts — Total Discounts
        - shipping_amount — Shipping Amount
        - cancel_reason — Cancel Reason
        - cancelled_at — Cancelled At
        - note — Note
        - refund_amount — Refund Amount
        - $source — Source
        - $import — Import
        - utm_source — UTM Source
        - utm_medium — UTM Medium
        - utm_campaign — UTM Campaign
        - utm_content — UTM Content
        - utm_term — UTM Term
        - event_type — Event Type
        - vendo_tracking_version — Vendo Tracking Version
        """
    )
)


query_runner_agent = Agent(
    name="query_runner",
    model="gemini-2.0-flash",
    description="Builds & executes the Mixpanel query, returns raw rows.",
    instruction=(
        "Use the run_mixpanel_query tool to fetch data for the selected events. "
        "Return the rows exactly as received."
    ),
    tools=[query_event],
    output_key="mixpanel_rows",
)


researcher = Agent(
    name="research_planner_agent",
    model="gemini-2.0-flash",
    description="Plans the parameters of the research",
    instruction=(
        """
        1. Use the select_event_agent to findout which events are the closest to customers request"
        2. If the have a date range use that, if not ask client the data range of the research. If client doesn't respond does the last 30 days from today
        3. Clarify why the parameters of the research are.  
        Example output:
            from_date=from_date,
            to_date=to_date,
            event_names=["Order Received","Order Refunded"],
        4. Use the query_mixpanel tool to fetch the data using the parameters in step 3. Only run this once. `
        5. Display the data in a table format.
        """
    ),
    tools=[
        AgentTool(agent=select_event_agent),
        AgentTool(agent=query_runner_agent),
        query_mixpanel
    ]
)


# ────────────────────────────────────────────────────────────────────────────
# 3. Root orchestration agent
# ────────────────────────────────────────────────────────────────────────────

root_agent = Agent(
    name="agent_router",
    model="gemini-2.0-flash-exp",
    description="Job is to route the user's request to the right sub-agent.",
    instruction=(
        """
        You are a helpful analytics assistant. Understand the user's request and route it to the right sub-agent.

        If the client is asking about a research. i.e how much revenue we made last month. Route the request to the researcher agent.
            
        Ask clarifying questions if needed.
        If you can't find the right sub-agent, just say "I don't know"
        """
    ),
    sub_agents=[ #sub agents will take over the task. Root agent will only orchestrate the sub agents.
        researcher 
    ],
)
