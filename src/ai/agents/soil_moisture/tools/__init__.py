"""Tool layer for the SoilMoistureAgent (AGENT-HYD-SM-001).

For MVP, this agent uses template-based analysis without external tool calls.
Tools required per PRD:
- GIS tools (raster stats) → delegated to M4's geospatial_tools.py
- Analytics tools (time series) → delegated to M4's llm_tools.py
- DB tools (historical data) → delegated to ContextEngine

When LLM-powered analysis is added, register tools via M4's AgentRuntime:
    runtime.register_tool(GeospatialQueryTool())
    runtime.register_tool(TimeSeriesTool())
"""
