"""Runtime extensions for the SoilMoistureAgent (AGENT-HYD-SM-001).

The agent's execute() logic lives in agent.py loaded by M4's AgentRuntime.
This module is reserved for agent-specific runtime configuration:

- Execution limits (defined in manifest.yaml)
- Tool allowlist (defined in manifest.yaml)
- Custom runtime middleware (future)
- Post-processing hooks (future)
"""
