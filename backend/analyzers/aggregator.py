from .models import AnalysisResult


VERDICT_SCORES = {
    AnalysisResult.Verdict.AUTHENTIC: 0.0,
    AnalysisResult.Verdict.SUSPICIOUS: 0.5,
    AnalysisResult.Verdict.FAKE: 1.0,
    AnalysisResult.Verdict.INCONCLUSIVE: 0.5,
}

DECISIVE_VERDICTS = {
    AnalysisResult.Verdict.AUTHENTIC,
    AnalysisResult.Verdict.SUSPICIOUS,
    AnalysisResult.Verdict.FAKE,
}

CORROBORATION_CONFIDENCE_FLOOR = 0.55
MIN_CORROBORATING_FOR_FAKE = 2


def aggregate(results: list[AnalysisResult]) -> tuple[float, str]:
    valid_results = [r for r in results if r.verdict != AnalysisResult.Verdict.ERROR]

    if not valid_results:
        return 0.5, "inconclusive"

    decisive_results = [r for r in valid_results if r.verdict in DECISIVE_VERDICTS]
    if not decisive_results:
        return 0.5, "inconclusive"

    total_weight = 0.0
    weighted_score = 0.0

    for result in valid_results:
        effective_weight = result.analyzer.weight * result.confidence
        base_score = VERDICT_SCORES.get(result.verdict, 0.5)
        weighted_score += base_score * effective_weight
        total_weight += effective_weight

    final_score = weighted_score / total_weight if total_weight > 0 else 0.5

    confident_decisive = [r for r in decisive_results if r.confidence >= CORROBORATION_CONFIDENCE_FLOOR]
    confident_verdicts = {r.verdict for r in confident_decisive}
    fake_voters = [r for r in confident_decisive if r.verdict in (AnalysisResult.Verdict.FAKE, AnalysisResult.Verdict.SUSPICIOUS)]
    authentic_voters = [r for r in confident_decisive if r.verdict == AnalysisResult.Verdict.AUTHENTIC]

    has_disagreement = (
        len(confident_verdicts) > 1
        and AnalysisResult.Verdict.AUTHENTIC in confident_verdicts
        and (
            AnalysisResult.Verdict.FAKE in confident_verdicts
            or AnalysisResult.Verdict.SUSPICIOUS in confident_verdicts
        )
    )

    if has_disagreement:
        return round(final_score, 4), "needs_review"

    raw_verdict = _band(final_score)

    if raw_verdict in ("fake", "likely_fake") and len(fake_voters) < MIN_CORROBORATING_FOR_FAKE:
        raw_verdict = "suspicious" if raw_verdict == "fake" else "inconclusive"

    if raw_verdict == "authentic" and len(authentic_voters) < 1:
        raw_verdict = "inconclusive"

    return round(final_score, 4), raw_verdict


def _band(score: float) -> str:
    if score < 0.25:
        return "authentic"
    if score < 0.45:
        return "suspicious"
    if score < 0.55:
        return "inconclusive"
    if score < 0.78:
        return "likely_fake"
    return "fake"
