"""Tool layer for the WeatherAgent (AGENT-HYD-MET-001).

For MVP, this agent uses template-based analysis without external tool calls.
Tools required per PRD:
- Weather tools (API SMN / OpenMeteo) → future: register via AgentRuntime
- Analytics tools (anomaly detection) → future: register via AgentRuntime

The agent consumes pre-built context from ContextEngine which already
integrates weather data from available sources (SMN, OpenMeteo, etc.).
"""
