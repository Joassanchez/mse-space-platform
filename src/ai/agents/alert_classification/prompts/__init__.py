"""Prompt templates for AlertClassificationAgent."""

NL_TEMPLATE = (
    "Alert classification: {severity} ({event_type}). "
    "Zones affected: {zones}. "
    "Data confidence: {confidence:.0%}."
)
