from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


# ============================================================================
# FIN-BENCH CASE
# ============================================================================


@dataclass(frozen=True, slots=True)
class BenchCase:
    """
    One deterministic FIN-Bench case.
    """

    case_id: str
    domain: str
    prompt: str
    expected: str
    required_terms: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()


# ============================================================================
# FIN-BENCH SCORE
# ============================================================================


@dataclass(frozen=True, slots=True)
class BenchScore:
    """
    Result for one FIN-Bench case.
    """

    case_id: str
    domain: str
    response: str

    exact_match: bool
    evidence_score: float

    @property
    def passed(self) -> bool:
        """
        Backward-compatible result property.

        A case passes when either:
        1. the normalized response exactly matches expected, or
        2. all required terms are present.
        """

        return (
            self.exact_match
            or self.evidence_score >= 1.0
        )


# ============================================================================
# FIN-BENCH ENGINE
# ============================================================================


class FINBench:
    """
    Deterministic finance-model benchmark.

    This evaluates controlled finance reasoning/task compliance.

    It is NOT a market-performance benchmark.
    """

    def __init__(
        self,
        cases: Iterable[BenchCase],
    ) -> None:

        self.cases = tuple(cases)

    @staticmethod
    def _normalize(
        value: str,
    ) -> str:

        return " ".join(
            str(value)
            .strip()
            .lower()
            .split()
        )

    @staticmethod
    def _evidence_score(
        response: str,
        required_terms: tuple[str, ...],
    ) -> float:

        if not required_terms:
            return 1.0

        normalized = response.lower()

        matched = sum(
            term.lower() in normalized
            for term in required_terms
        )

        return (
            matched
            / len(required_terms)
        )

    def run(
        self,
        model: Callable[[str], str],
    ) -> tuple[BenchScore, ...]:

        results: list[BenchScore] = []

        for case in self.cases:

            response = str(
                model(case.prompt)
            )

            normalized_response = (
                self._normalize(response)
            )

            normalized_expected = (
                self._normalize(case.expected)
            )

            exact_match = (
                normalized_response
                == normalized_expected
            )

            evidence_score = (
                self._evidence_score(
                    response,
                    case.required_terms,
                )
            )

            results.append(
                BenchScore(
                    case_id=case.case_id,
                    domain=case.domain,
                    response=response,
                    exact_match=exact_match,
                    evidence_score=evidence_score,
                )
            )

        return tuple(results)

    @staticmethod
    def aggregate(
        results: Iterable[BenchScore],
    ) -> dict:

        rows = tuple(results)

        if not rows:
            return {
                "cases": 0,
                "pass_rate": 0.0,
                "exact_rate": 0.0,
                "evidence_coverage": 0.0,
                "domains": {},
            }

        domains: dict[
            str,
            list[BenchScore],
        ] = {}

        for result in rows:

            domains.setdefault(
                result.domain,
                [],
            ).append(result)

        return {
            "cases": len(rows),

            "pass_rate": (
                sum(
                    result.passed
                    for result in rows
                )
                / len(rows)
            ),

            "exact_rate": (
                sum(
                    result.exact_match
                    for result in rows
                )
                / len(rows)
            ),

            "evidence_coverage": (
                sum(
                    result.evidence_score
                    for result in rows
                )
                / len(rows)
            ),

            "domains": {
                domain: {
                    "cases": len(
                        domain_results
                    ),
                    "pass_rate": (
                        sum(
                            result.passed
                            for result
                            in domain_results
                        )
                        / len(domain_results)
                    ),
                    "exact_rate": (
                        sum(
                            result.exact_match
                            for result
                            in domain_results
                        )
                        / len(domain_results)
                    ),
                    "evidence_coverage": (
                        sum(
                            result.evidence_score
                            for result
                            in domain_results
                        )
                        / len(domain_results)
                    ),
                }
                for domain, domain_results
                in sorted(
                    domains.items()
                )
            },
        }


# ============================================================================
# EXISTING DELTA FIN-BENCH PUBLIC API
# ============================================================================


FIN_BENCH_DIMS = (
    "market_reasoning",
    "risk",
    "portfolio",
    "macro",
    "quantitative",
    "financial_analysis",
    "uncertainty",
    "tool_use",
    "regulatory",
    "sustainability",
    "liquidity",
    "execution",
)


def finbench_dataset() -> tuple[BenchCase, ...]:
    """
    Return the built-in deterministic FIN-Bench dataset.

    The dataset is intentionally deterministic so that unit tests,
    development evaluation and CI remain reproducible.
    """

    return (
        BenchCase(
            case_id="market-001",
            domain="market_reasoning",
            prompt=(
                "What should be considered before "
                "making a market decision?"
            ),
            expected="evidence",
            required_terms=("evidence",),
        ),

        BenchCase(
            case_id="risk-001",
            domain="risk",
            prompt=(
                "What should happen when uncertainty "
                "is too high?"
            ),
            expected="wait",
            required_terms=("wait",),
        ),

        BenchCase(
            case_id="portfolio-001",
            domain="portfolio",
            prompt=(
                "What should be checked before "
                "changing a portfolio?"
            ),
            expected="risk",
            required_terms=("risk",),
        ),

        BenchCase(
            case_id="macro-001",
            domain="macro",
            prompt=(
                "What should a macro analysis use?"
            ),
            expected="evidence",
            required_terms=("evidence",),
        ),

        BenchCase(
            case_id="quant-001",
            domain="quantitative",
            prompt=(
                "What should quantitative research "
                "use to validate a strategy?"
            ),
            expected="backtest",
            required_terms=("backtest",),
        ),

        BenchCase(
            case_id="financial-analysis-001",
            domain="financial_analysis",
            prompt=(
                "What should financial analysis "
                "use to support a conclusion?"
            ),
            expected="evidence",
            required_terms=("evidence",),
        ),

        BenchCase(
            case_id="uncertainty-001",
            domain="uncertainty",
            prompt=(
                "What should a system do when it "
                "cannot establish sufficient confidence?"
            ),
            expected="abstain",
            required_terms=("abstain",),
        ),

        BenchCase(
            case_id="tool-use-001",
            domain="tool_use",
            prompt=(
                "What should an autonomous financial "
                "system do before using a restricted tool?"
            ),
            expected="authorize",
            required_terms=("authorize",),
        ),

        BenchCase(
            case_id="regulatory-001",
            domain="regulatory",
            prompt=(
                "What should be considered when "
                "making a trading decision?"
            ),
            expected="compliance",
            required_terms=("compliance",),
        ),

        BenchCase(
            case_id="sustainability-001",
            domain="sustainability",
            prompt=(
                "What should be evaluated when "
                "assessing long-term investment viability?"
            ),
            expected="esg",
            required_terms=("esg",),
        ),

        BenchCase(
            case_id="liquidity-001",
            domain="liquidity",
            prompt=(
                "What should be checked before "
                "executing a large order?"
            ),
            expected="liquidity",
            required_terms=("liquidity",),
        ),

        BenchCase(
            case_id="execution-001",
            domain="execution",
            prompt=(
                "What should be optimized when "
                "trading large positions?"
            ),
            expected="slippage",
            required_terms=("slippage",),
        ),
    )


def score_suite(
    cases: Iterable[BenchCase],
    answers: dict[str, tuple[str, tuple[str, ...]]],
) -> list:
    """
    Score a suite of FIN-Bench cases against expected answers.

    Returns a list of score objects with a 'score' attribute.
    """
    from decimal import Decimal

    scores = []
    for case in cases:
        if case.case_id in answers:
            expected, evidence_ids = answers[case.case_id]
            # Simple scoring: if expected matches, score is 1.0, else 0.0
            match_score = Decimal("1.0") if case.expected == expected else Decimal("0.0")
            scores.append(type('Score', (), {'score': match_score})())
        else:
            scores.append(type('Score', (), {'score': Decimal("0.0")})())
    return scores


# ============================================================================
# FIN-BENCH RELEASE GATE (12-dim + grounding)
# ============================================================================


def citation_coverage(
    responses: dict[str, str],
    evidence_ids: dict[str, tuple[str, ...]],
) -> float:
    """Fraction of responses citing at least one evidence id ([id] format)."""
    from finance_model.grounding import verify_grounding

    if not responses:
        return 0.0
    supported = 0
    for case_id, response in responses.items():
        checks = verify_grounding((response,), evidence_ids.get(case_id, ()))
        if checks and all(c.supported for c in checks):
            supported += 1
    return supported / len(responses)


def finbench_gate(
    results: Iterable[BenchScore],
    *,
    min_pass_rate: float = 1.0,
    min_domain_rate: float = 1.0,
) -> dict:
    """Release gate: global + every-domain pass rates must meet thresholds."""
    summary = FINBench.aggregate(results)
    domains = summary.get("domains", {})
    weak = sorted(
        d for d, s in domains.items() if s.get("pass_rate", 0.0) < min_domain_rate
    )
    passed = bool(summary.get("cases", 0)) and summary.get("pass_rate", 0.0) >= min_pass_rate and not weak
    return {**summary, "passed": passed, "weak_domains": weak}


# ============================================================================
# SIMPLE MODULE SELF-TEST
# ============================================================================


if __name__ == "__main__":

    benchmark = FINBench(
        [
            BenchCase(
                case_id="self-test",
                domain="risk",
                prompt="What action?",
                expected="WAIT",
                required_terms=("wait",),
            )
        ]
    )

    results = benchmark.run(
        lambda _: "WAIT"
    )

    assert results[0].passed

    summary = FINBench.aggregate(
        results
    )

    assert summary["cases"] == 1
    assert summary["pass_rate"] == 1.0

    print(
        "FIN-Bench self-test: PASS"
    )