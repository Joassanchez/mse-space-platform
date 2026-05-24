"""Natural language output templates for the RiskClassificationAgent."""

UNAVAILABLE_MSG = "Risk data is currently unavailable for this region."

NL_TEMPLATE = (
    "Risk classification: {risk_level} (score: {score:.2f}). "
    "Contributing factors: {factors}. "
    "Data confidence: {confidence:.0%}."
)
