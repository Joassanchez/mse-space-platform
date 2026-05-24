"""Natural language output templates for ExecutiveSummaryAgent."""

EXEC_TEMPLATE = (
    "Resumen ejecutivo — {severity}: {event_type}. "
    "Situación: {situation}. "
    "Riesgo: {risk}. "
    "Acciones recomendadas: {actions}. "
    "Confianza: {confidence:.0%}."
)
