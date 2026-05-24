"""Natural language output templates for the PredictiveScenariosAgent."""

UNAVAILABLE_MSG = "Scenario projection data is currently unavailable."

NL_TEMPLATE = (
    "Scenario projections: {count} scenario(s). "
    "Probable (7d): {probable_7d}. "
    "Data confidence: {confidence:.0%}."
)
