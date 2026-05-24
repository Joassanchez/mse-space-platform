"""Natural language output templates for the SoilMoistureAgent.

Template-based, deterministic — no LLM calls.
Includes basic recommendation per PRD §5.4.1.
"""

from src.ai.domain.models import SoilMoistureStatus

# Template strings
UNAVAILABLE_MSG = "Soil moisture data is currently unavailable for this region."

NL_TEMPLATE = (
    "Soil moisture status at {status} level. "
    "Surface: {surface} ({surface_status}). "
    "Rootzone: {rootzone} ({rootzone_status}). "
    "Trend: {trend}. "
    "Data confidence: {confidence:.0%}.{recommendation}"
)

# Recommendation mapping based on worst status
RECOMMENDATIONS = {
    SoilMoistureStatus.CRITICAL_DRY: " Se recomienda riego urgente.",
    SoilMoistureStatus.DRY: " Se recomienda monitorear y considerar riego.",
    SoilMoistureStatus.NORMAL: " Sin necesidad de intervención.",
    SoilMoistureStatus.WET: " Monitorear drenaje en zonas bajas.",
    SoilMoistureStatus.CRITICAL_WET: (
        " Se recomienda verificar drenaje y posibles anegamientos."
    ),
    SoilMoistureStatus.UNAVAILABLE: "",
}
