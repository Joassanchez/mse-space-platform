"""Natural language output templates for the TerritorialPrioritizationAgent."""

UNAVAILABLE_MSG = "Territorial data is currently unavailable for this region."

NL_TEMPLATE = (
    "Priority zones identified: {count} zone(s). "
    "Top priority: {top}. "
    "Data confidence: {confidence:.0%}."
)
