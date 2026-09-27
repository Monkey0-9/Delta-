
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FinancialEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    observation: str = Field(min_length=1)
    reliability: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))


class FinancialAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument: str = Field(min_length=1)
    world_state_version: str = Field(min_length=1)
    quant_state_version: str = Field(min_length=1)
    portfolio_context: str = Field(min_length=1)
    horizon: str = Field(min_length=1)

    expected_return: Decimal
    uncertainty: Decimal = Field(
        ge=Decimal("0"),
        le=Decimal("1"),
    )

    evidence: tuple[FinancialEvidence, ...] = ()

    stress_summary: str | None = None


class FinancialAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument: str
    thesis: str
    horizon: str
    expected_return: Decimal
    confidence: Decimal = Field(
        ge=Decimal("0"),
        le=Decimal("1"),
    )

    risks: tuple[str, ...]
    uncertainty_sources: tuple[str, ...]
    evidence: tuple[FinancialEvidence, ...]

    scenario_analysis: str
    candidate_action: str

    invalidating_conditions: tuple[str, ...]

    model_version: str = Field(min_length=1)
