"""Natural language output templates for the WeatherAgent.

Template-based, deterministic — no LLM calls.
Includes all PRD §5.4.4 fields: rainfall, temperature, humidity, wind.
"""

UNAVAILABLE_MSG = "Weather data is currently unavailable for this region."

NL_TEMPLATE = (
    "Rainfall: 30d={rainfall_30d} (anomaly: {anomaly}, "
    "condition: {condition}), 7d={rainfall_7d}. "
    "Temperature: avg={temp_avg}, anomaly={temp_anom}. "
    "Humidity: {humidity}. Wind: {wind}. "
    "Data confidence: {confidence:.0%}."
)
