# Business Data Context

This folder contains business-specific data files that are loaded by the agent to provide business context for personalized responses.

## Purpose

- Provides business context to the agent
- Allows for personalized responses based on company information
- Enables data-driven recommendations

## File Format

All files in this directory should be valid JSON files. Each file will be loaded as a separate section of business data, with the filename (minus extension) used as the section key.

For example, a file named `company_profile.json` will be accessible as the `company_profile` section.

## Accessing Data

The agent has several tools to work with this business data:

1. **business_context_summary_tool**: Lists all available business data sections
2. **business_context_section_tool**: Retrieves a specific section of business data
3. **business_context_search_tool**: Searches for relevant information across all business data

## Adding New Data

To add new business context data:

1. Create a new JSON file in this directory with a descriptive name
2. Ensure the file contains valid JSON data
3. The agent will automatically load the new file on the next conversation

## Current Data Files

- `company_profile.json`: Basic information about the company including name, industry, size, products, and goals
- `market_analysis.json`: Market overview, segmentation, competitive landscape, and growth opportunities

## Data Structure

There is no required structure for the JSON files as long as they contain valid JSON. However, it's recommended to organize data in a logical hierarchy to make it easier for the agent to access and reference specific information. 