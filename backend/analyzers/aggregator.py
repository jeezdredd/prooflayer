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
MANIPULATION_ANALYZERS = {"ela", "metadata"}

CORROBORATION_CONFIDENCE_FLOOR = 0.5
MIN_CORROBORATING_FOR_FAKE = 2
CF_PRIORITY_THRESHOLD = 0.92
CF_PRIORITY_PEERS = {"npr_detector", "siglip_detector"}
AUTHENTIC_EDITED_AI_CEIL = 0.30


def _get_ai_probability(result) -> float | None:
    if result.analyzer.name not in PROBABILISTIC_ANALYZERS:
        return None
    ai_prob = (result.evidence or {}).get("ai_probability")
    if ai_prob is None:
        return None
    return float(ai_prob)


def _community_forensics_priority(all_results) -> bool:
    cf = next(
        (r for r in all_results if r.analyzer.name == "community_forensics"),
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
        for r in all_results
    )


def _has_manipulation_signal(valid_results) -> bool:
    for r in valid_results:
        if r.analyzer.name not in MANIPULATION_ANALYZERS:
            continue
        if r.verdict in (AnalysisResult.Verdict.SUSPICIOUS, AnalysisResult.Verdict.FAKE):
            return True
    return False


def aggregate(results: list[AnalysisResult]) -> tuple[float, str]:
    valid_results = [r for r in results if r.verdict != AnalysisResult.Verdict.ERROR]
    if not valid_results:
        return 0.5, "inconclusive"

    decisive_results = [r for r in valid_results if r.verdict in DECISIVE_VERDICTS]

    total_weight = 0.0
    weighted_score = 0.0

    prob_results = [r for r in valid_results if r.analyzer.name in PROBABILISTIC_ANALYZERS]
    prob_names = {r.analyzer.name for r in prob_results}
    non_prob_decisive = [r for r in decisive_results if r.analyzer.name not in PROBABILISTIC_ANALYZERS]

    for result in prob_results:
        ai_prob = _get_ai_probability(result)
        if ai_prob is not None:
            weighted_score += ai_prob * result.analyzer.weight
            total_weight += result.analyzer.weight

    for result in non_prob_decisive:
        effective_weight = result.analyzer.weight * result.confidence
        base_score = VERDICT_SCORES.get(result.verdict, 0.5)
        weighted_score += base_score * effective_weight
        total_weight += effective_weight

    if total_weight == 0:
        return 0.5, "inconclusive"

    final_score = weighted_score / total_weight

    if _community_forensics_priority(valid_results):
        return round(max(final_score, 0.85), 4), "fake"

    fake_voters = []
    authentic_voters = []
    for r in valid_results:
        ai_prob = _get_ai_probability(r)
        if ai_prob is not None:
            prob_conf = abs(ai_prob - 0.5) * 2
            if prob_conf >= CORROBORATION_CONFIDENCE_FLOOR:
                if ai_prob >= 0.5:
                    fake_voters.append(r)
                else:
                    authentic_voters.append(r)
        elif r.verdict in DECISIVE_VERDICTS:
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

    if raw_verdict == "authentic" and len(authentic_voters) < 1 and total_weight > 0:
        raw_verdict = "inconclusive"

    if raw_verdict in ("authentic", "inconclusive") and final_score < AUTHENTIC_EDITED_AI_CEIL:
        if _has_manipulation_signal(valid_results):
            return round(final_score, 4), "authentic_edited"

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
