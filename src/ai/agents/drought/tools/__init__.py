"""Tool layer for the DroughtAgent (AGENT-HYD-DR-001).

For MVP, this agent uses template-based analysis without external tool calls.
Tools required per PRD:
- Analytics tools (SPI calculation) → future: register via AgentRuntime
- GIS tools (drought extent mapping) → future: register via AgentRuntime
- DB tools (historical climatology) → delegated to ContextEngine

SPI values are consumed from ContextEngine indicators (pre-computed).
"""
