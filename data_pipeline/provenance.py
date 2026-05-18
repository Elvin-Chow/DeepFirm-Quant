"""Shared data quality provenance contracts."""

from collections.abc import Iterable
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class DataQuality(BaseModel):
    """Response-level data quality and provenance summary."""

    asof_date: Optional[str] = Field(default=None)
    coverage_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    calendar: str = Field(default="unknown")
    cache_status: str = Field(default="unknown")
    is_stale: bool = Field(default=False)
    is_partial: bool = Field(default=False)
    provider_chain: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @staticmethod
    def _unique_strings(values: object) -> List[str]:
        if values is None:
            return []
        if isinstance(values, str):
            raw_values: Iterable[object] = [values]
        else:
            raw_values = values if isinstance(values, Iterable) else [values]

        seen: set[str] = set()
        clean_values: List[str] = []
        for value in raw_values:
            text = str(value).strip()
            if text and text not in seen:
                clean_values.append(text)
                seen.add(text)
        return clean_values

    @field_validator("provider_chain", "warnings", mode="before")
    @classmethod
    def normalize_string_list(cls, values: object) -> List[str]:
        return cls._unique_strings(values)

    def with_warnings(self, warnings: Iterable[str]) -> "DataQuality":
        """Return a copy with merged warning text."""
        merged = [*self.warnings, *[str(warning) for warning in warnings]]
        return self.model_copy(update={"warnings": self._unique_strings(merged)})
