"""Ranking service: deterministic ordering of candidates by score."""

from __future__ import annotations

from app.services.matching_service import MatchBreakdown


def rank_breakdowns(breakdowns: list[MatchBreakdown]) -> list[tuple[int, MatchBreakdown]]:
    """Sort by overall score desc, with stable deterministic tie-breakers.

    Tie-breakers: higher skill score, then higher semantic score. Returns
    1-indexed ``(rank, breakdown)`` pairs.
    """

    ordered = sorted(
        breakdowns,
        key=lambda b: (-b.overall_score, -b.skill_score, -b.semantic_score, -b.evidence_score),
    )
    return [(index, breakdown) for index, breakdown in enumerate(ordered, start=1)]


def summarize(scored: list[tuple[int, MatchBreakdown]]) -> dict:
    """Headline stats for the dashboard."""

    scores = [breakdown.overall_score for _, breakdown in scored]
    if not scores:
        return {
            "total_candidates": 0,
            "average_match": 0.0,
            "top_score": 0.0,
            "lowest_score": 0.0,
            "median_score": 0.0,
            "above_70": 0,
            "above_50": 0,
        }

    ordered = sorted(scores)
    middle = len(ordered) // 2
    median = (
        ordered[middle]
        if len(ordered) % 2 == 1
        else round((ordered[middle - 1] + ordered[middle]) / 2, 2)
    )

    return {
        "total_candidates": len(scores),
        "average_match": round(sum(scores) / len(scores), 2),
        "top_score": round(max(scores), 2),
        "lowest_score": round(min(scores), 2),
        "median_score": round(median, 2),
        "above_70": sum(1 for s in scores if s >= 70),
        "above_50": sum(1 for s in scores if s >= 50),
    }