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

PROBABILISTIC_ANALYZERS = {"community_forensics", "npr_detector", "siglip_detector", "llm_vision"}

CORROBORATION_CONFIDENCE_FLOOR = 0.5
MIN_CORROBORATING_FOR_FAKE = 2
CF_PRIORITY_THRESHOLD = 0.92
CF_PRIORITY_PEERS = {"npr_detector", "siglip_detector"}


def _get_ai_probability(result) -> float | None:
    if result.analyzer.name not in PROBABILISTIC_ANALYZERS:
        return None
    ai_prob = (result.evidence or {}).get("ai_probability")
    if ai_prob is None:
        return None
    return float(ai_prob)


def _community_forensics_priority(decisive_results) -> bool:
    cf = next(
        (r for r in decisive_results if r.analyzer.name == "community_forensics" and r.verdict == AnalysisResult.Verdict.FAKE),
        None,
    )
    if cf is None:
        return False
    ai_prob = (cf.evidence or {}).get("ai_probability", 0.0)
    if ai_prob < CF_PRIORITY_THRESHOLD:
        return False
    return any(
        r.analyzer.name in CF_PRIORITY_PEERS
        and r.verdict in (AnalysisResult.Verdict.FAKE, AnalysisResult.Verdict.SUSPICIOUS)
        for r in decisive_results
    )


def aggregate(results: list[AnalysisResult]) -> tuple[float, str]:
    valid_results = [r for r in results if r.verdict != AnalysisResult.Verdict.ERROR]
    if not valid_results:
        return 0.5, "inconclusive"

    decisive_results = [r for r in valid_results if r.verdict in DECISIVE_VERDICTS]
    if not decisive_results:
        return 0.5, "inconclusive"

    total_weight = 0.0
    weighted_score = 0.0

    for result in decisive_results:
        ai_prob = _get_ai_probability(result)
        if ai_prob is not None:
            effective_weight = result.analyzer.weight
            weighted_score += ai_prob * effective_weight
        else:
            effective_weight = result.analyzer.weight * result.confidence
            base_score = VERDICT_SCORES.get(result.verdict, 0.5)
            weighted_score += base_score * effective_weight
        total_weight += effective_weight

    final_score = weighted_score / total_weight if total_weight > 0 else 0.5

    if _community_forensics_priority(decisive_results):
        return round(max(final_score, 0.85), 4), "fake"

    fake_voters = []
    authentic_voters = []
    for r in decisive_results:
        ai_prob = _get_ai_probability(r)
        if ai_prob is not None:
            prob_conf = abs(ai_prob - 0.5) * 2
            if prob_conf >= CORROBORATION_CONFIDENCE_FLOOR:
                if ai_prob >= 0.5:
                    fake_voters.append(r)
                else:
                    authentic_voters.append(r)
        else:
            if r.confidence >= CORROBORATION_CONFIDENCE_FLOOR:
                if r.verdict in (AnalysisResult.Verdict.FAKE, AnalysisResult.Verdict.SUSPICIOUS):
                    fake_voters.append(r)
                elif r.verdict == AnalysisResult.Verdict.AUTHENTIC:
                    authentic_voters.append(r)

    has_disagreement = len(fake_voters) >= 2 and len(authentic_voters) >= 2
    if has_disagreement:
        return round(final_score, 4), "needs_review"

    raw_verdict = _band(final_score)

    if raw_verdict in ("fake", "likely_fake") and len(fake_voters) < MIN_CORROBORATING_FOR_FAKE:
        raw_verdict = "suspicious" if raw_verdict == "fake" else "inconclusive"

    if raw_verdict == "authentic" and len(authentic_voters) < 1:
        raw_verdict = "inconclusive"

    return round(final_score, 4), raw_verdict


def _band(score: float) -> str:
    if score < 0.35:
        return "authentic"
    if score < 0.5:
        return "suspicious"
    if score < 0.6:
        return "inconclusive"
    if score < 0.75:
        return "likely_fake"
    return "fake"
