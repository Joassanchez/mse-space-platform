"""INDEC Socioeconomic Data Connector (Design / Contract).

Flujo conceptual:
  INDEC API / CSV / XLSX → IndecConnector.fetch() → parser → normalización
  → PostgreSQL (indicators + metadata) → ContextEngine → EconomicOrchestrator

Para MVP:
  - No se implementa el conector real.
  - Los datos demo se cargan via seeds/003_socioeconomic_demo.sql.
  - Este archivo define el CONTRATO (interfaz + método esperado) para
    implementación futura cuando haya acceso a fuentes reales.

Uso futuro esperado:
  connector = IndecConnector()
  connector.fetch(region_id=1, dataset="crop_yields", year=2024)
  → inserta en indicators con indicator_code="ECO_CROP_YIELD" + metadata={"source":"indec","demo":false}
"""

from typing import Any, Optional

from src.geospatial.domain.models import Indicator


class IndecConnector:
    """Connector for INDEC socioeconomic data (design contract only).

    Attributes:
        source_code: Identificador de fuente ("indec", "indec_api", "indec_csv").
        base_url: URL base de la API de INDEC (futuro).
    """

    SOURCE_CODE = "indec"
    BASE_URL = "https://apis.datos.gob.ar/series/api/series"  # FUTURO

    def __init__(self):
        self.name = "indec-connector"

    def fetch(
        self,
        region_id: int,
        dataset: str,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch socioeconomic indicators from INDEC.

        Args:
            region_id: Región a consultar.
            dataset: Tipo de dataset ("crop_yields", "commodity_prices",
                     "population", "employment", "poverty").
            year: Año de referencia (opcional, usa último disponible si se omite).

        Returns:
            Lista de indicadores normalizados con formato Indicator-compatible.

        Raises:
            NotImplementedError: Siempre en MVP — implementar cuando haya
                                 acceso a API real o datasets oficiales.
        """
        raise NotImplementedError(
            f"IndecConnector.fetch() no está implementado en MVP. "
            f"Solicitado: dataset={dataset}, region={region_id}, year={year}. "
            f"Usar seeds/003_socioeconomic_demo.sql para datos demo."
        )

    @staticmethod
    def parse_csv(file_path: str) -> list[dict[str, Any]]:
        """Parsear un archivo CSV con formato INDEC estándar.

        Formato esperado:
          periodo,region_id,indicador,valor,unidad
          2024,1,ECO_CROP_YIELD,4500.0,kg/ha

        Returns:
            Lista de dicts normalizados listos para insertar en indicators.

        Raises:
            NotImplementedError: En MVP.
        """
        raise NotImplementedError(
            "IndecConnector.parse_csv() no está implementado en MVP."
        )

    @staticmethod
    def to_indicator(
        raw: dict[str, Any],
        source: str = "indec",
        is_demo: bool = True,
    ) -> Indicator:
        """Convertir un dict normalizado a un Indicator del dominio.

        Args:
            raw: Dict con keys: indicator_code, indicator_name, value,
                 unit, region_id, temporal_start, temporal_end.
            source: Fuente de datos.
            is_demo: True si es dato de referencia/demo, False si es real.

        Returns:
            Indicator listo para persistir.
        """
        from datetime import date

        return Indicator(
            region_id=raw["region_id"],
            indicator_code=raw["indicator_code"],
            indicator_name=raw.get("indicator_name", raw["indicator_code"]),
            value=raw["value"],
            unit=raw.get("unit", ""),
            classification="reference" if is_demo else "official",
            confidence=0.5 if is_demo else 0.8,
            temporal_start=raw.get("temporal_start", f"{date.today().year}-01-01"),
            temporal_end=raw.get("temporal_end", f"{date.today().year}-12-31"),
            metadata={
                "source": source,
                "is_demo": is_demo,
                "note": "DEMO DATA — not actual INDEC data" if is_demo else "",
            },
        )
