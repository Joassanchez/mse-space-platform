"""Natural language output templates for the DroughtAgent.

Template-based, deterministic — no LLM calls.
Includes short-term projection per PRD §5.4.3.
"""

UNAVAILABLE_MSG = "Drought data is currently unavailable for this region."

NL_TEMPLATE = (
    "Drought conditions: {category} (signal: {signal}). "
    "SPI 30d: {spi_30d}, SPI 90d: {spi_90d}. "
    "Trend: {trend}.{projection} "
    "Data confidence: {confidence:.0%}."
)

# Short-term projection based on trend (PRD §5.4.3)
PROJECTIONS = {
    "worsening": (
        " Si la tendencia actual se mantiene, las condiciones "
        "podrían agravarse en las próximas 2-4 semanas."
    ),
    "improving": (
        " La tendencia de mejora sugiere una recuperación "
        "gradual en las próximas semanas."
    ),
    "stable": " Sin cambios significativos esperados en el corto plazo.",
}
