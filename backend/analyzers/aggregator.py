from .models import AnalysisResult


VERDICT_SCORES = {
    AnalysisResult.Verdict.AUTHENTIC: 0.0,
    AnalysisResult.Verdict.SUSPICIOUS: 0.5,
    AnalysisResult.Verdict.FAKE: 1.0,
    AnalysisResult.Verdict.INCONCLUSIVE: 0.5,
}


def aggregate(results: list[AnalysisResult]) -> tuple[float, str]:
    valid_results = [r for r in results if r.verdict != AnalysisResult.Verdict.ERROR]

    if not valid_results:
        return 0.5, "inconclusive"

    total_weight = 0.0
    weighted_score = 0.0

    for result in valid_results:
        weight = result.analyzer.weight
        base_score = VERDICT_SCORES.get(result.verdict, 0.5)
        score = base_score * result.confidence + (1 - result.confidence) * 0.5
        weighted_score += score * weight
        total_weight += weight

    final_score = weighted_score / total_weight if total_weight > 0 else 0.5

    verdicts = {r.verdict for r in valid_results}
    has_disagreement = len(verdicts) > 1 and AnalysisResult.Verdict.AUTHENTIC in verdicts and (
        AnalysisResult.Verdict.FAKE in verdicts or AnalysisResult.Verdict.SUSPICIOUS in verdicts
    )

    if has_disagreement:
        final_verdict = "needs_review"
    elif final_score < 0.3:
        final_verdict = "authentic"
    elif final_score < 0.5:
        final_verdict = "suspicious"
    elif final_score < 0.7:
        final_verdict = "likely_fake"
    else:
        final_verdict = "fake"

    return round(final_score, 4), final_verdict
