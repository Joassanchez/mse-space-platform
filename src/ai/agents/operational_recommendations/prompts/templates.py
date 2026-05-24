"""Natural language output templates for OperationalRecommendationsAgent."""

NL_TEMPLATE = (
    "Recommended actions ({count}): highest priority — {top}. "
    "Data confidence: {confidence:.0%}."
)

# Versioned best practices indexed by event_type + severity (PRD §8.4.3)
BEST_PRACTICES = {
    "drought": {
        "critical": [
            ("Activar plan de emergencia hídrica", "high", "24 hs", "Municipio"),
            ("Coordinar distribución de agua", "high", "48 hs", "Defensa Civil"),
            ("Evaluar suspensión de riego", "medium", "72 hs", "Productores"),
        ],
        "alert": [
            ("Monitorear reservas de agua", "high", "24 hs", "Municipio"),
            ("Restringir riego no esencial", "medium", "48 hs", "Cooperativas"),
        ],
        "warning": [
            ("Actualizar inventario hídrico", "medium", "7 días", "Técnicos"),
        ],
    },
    "soil_moisture": {
        "critical": [
            ("Verificar sistemas de drenaje/riego", "high", "24 hs", "Técnicos"),
        ],
        "alert": [
            ("Monitorear evolución de humedad", "high", "48 hs", "Productores"),
        ],
    },
    "risk_escalation": {
        "critical": [
            ("Activar protocolo de emergencia", "high", "inmediato", "Municipio"),
            ("Evacuar zonas de alto riesgo", "high", "inmediato", "Defensa Civil"),
        ],
        "alert": [
            ("Preparar centros de evacuación", "high", "24 hs", "Municipio"),
        ],
    },
}

DEFAULT_ACTIONS = [
    ("Monitorear condiciones", "medium", "7 días", "Técnicos"),
]
