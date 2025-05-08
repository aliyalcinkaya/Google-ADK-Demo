import os
import json
import requests
import gzip
from typing import Optional, List

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