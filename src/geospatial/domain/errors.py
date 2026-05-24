"""Custom exceptions for the geospatial ETL pipeline.

All exceptions are source-agnostic and apply to any geospatial data source.
"""


class ValidationError(Exception):
    """Raised when a file or variable fails structural or range validation."""

    pass


class ReadError(Exception):
    """Raised when a geospatial file cannot be opened or read."""

    pass


class WriteError(Exception):
    """Raised when a GeoTIFF cannot be written to disk."""

    pass


class IdempotencySkip(Exception):
    """Raised when a processing attempt is skipped due to idempotency rules.

    The combination (raw_file_id, variable_name, processing_version) already
    exists, so processing is skipped and the existing layer should be returned.
    """

    def __init__(
        self,
        raw_file_id: int,
        variable_name: str,
        processing_version: str,
        existing_path: str | None = None,
    ):
        self.raw_file_id = raw_file_id
        self.variable_name = variable_name
        self.processing_version = processing_version
        self.existing_path = existing_path
        message = (
            f"Layer already exists: raw_file_id={raw_file_id}, "
            f"variable={variable_name}, version={processing_version}"
        )
        if existing_path:
            message += f", existing_path={existing_path}"
        super().__init__(message)
