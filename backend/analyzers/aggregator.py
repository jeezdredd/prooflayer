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

PROBABILITY_KEYS = ("ai_probability", "ai_probability_avg")
MANIPULATION_ANALYZERS = {"ela", "metadata"}

CORROBORATION_CONFIDENCE_FLOOR = 0.5
MIN_CORROBORATING_FOR_FAKE = 2
CF_PRIORITY_THRESHOLD = 0.92
CF_PRIORITY_PEERS = {"custom_detector", "ai_detector", "npr_detector", "siglip_detector"}
DISAGREEMENT_MIN_VOTERS = 2
DISAGREEMENT_MIN_MINORITY_SHARE = 0.3
SINGLE_VOTER_MIN_SHARE = 0.5
SINGLE_VOTER_MIN_PROB = 0.9
AUTHENTIC_EDITED_AI_CEIL = 0.30


def _get_ai_probability(result) -> float | None:
    evidence = result.evidence or {}
    for key in PROBABILITY_KEYS:
        raw = evidence.get(key)
        if raw is None:
            continue
        try:
            return min(max(float(raw), 0.0), 1.0)
        except (TypeError, ValueError):
            return None
    return None


def _community_forensics_priority(all_results) -> bool:
    cf = next(
        (r for r in all_results if r.analyzer.name == "community_forensics"),
        None,
    )
    if cf is None:
        return False
    ai_prob = _get_ai_probability(cf)
    if ai_prob is None or ai_prob < CF_PRIORITY_THRESHOLD:
        return False
    return any(
        r.analyzer.name in CF_PRIORITY_PEERS
        and r.verdict in (AnalysisResult.Verdict.FAKE, AnalysisResult.Verdict.SUSPICIOUS)
        for r in all_results
    )


def _has_weighted_disagreement(fake_voters, authentic_voters) -> bool:
    """Two camps of confident voters, and the lighter camp is not a rounding error.

    Counting heads let two low-weight, out-of-domain detectors (each saturated at
    p<0.01 on everything) manufacture needs_review against a heavy consensus.
    """
    if len(fake_voters) < DISAGREEMENT_MIN_VOTERS or len(authentic_voters) < DISAGREEMENT_MIN_VOTERS:
        return False
    fake_weight = sum(r.analyzer.weight for r in fake_voters)
    authentic_weight = sum(r.analyzer.weight for r in authentic_voters)
    total = fake_weight + authentic_weight
    if total <= 0:
        return False
    return min(fake_weight, authentic_weight) / total >= DISAGREEMENT_MIN_MINORITY_SHARE


def _single_dominant_fake_voter(fake_voters, authentic_voters, prob_scores) -> bool:
    """One fake voter may carry the verdict alone only when it dominates the bench.

    The two-corroborator rule exists to stop a single detector from convicting on its
    own. It also caps recall on generators that only one member has been trained on.
    Allow the exception when that member holds at least half of the confident-voter
    weight *and* is near-certain (p >= 0.9). Measured on 100 held-out real photos this
    kept real -> fake at zero; the naive "any single voter" variant did not.
    """
    if len(fake_voters) != 1:
        return False
    voter = fake_voters[0]
    prob = prob_scores.get(id(voter))
    if prob is None or prob < SINGLE_VOTER_MIN_PROB:
        return False
    fake_weight = voter.analyzer.weight
    total = fake_weight + sum(r.analyzer.weight for r in authentic_voters)
    return total > 0 and fake_weight / total >= SINGLE_VOTER_MIN_SHARE


def _has_manipulation_signal(valid_results) -> bool:
    for r in valid_results:
        if r.analyzer.name not in MANIPULATION_ANALYZERS:
            continue
        if (r.evidence or {}).get("manipulation_suspected"):
            return True
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

    prob_scores = {id(r): _get_ai_probability(r) for r in valid_results}
    non_prob_decisive = [r for r in decisive_results if prob_scores.get(id(r)) is None]

    for result in valid_results:
        ai_prob = prob_scores.get(id(result))
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
        ai_prob = prob_scores.get(id(r))
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

    if _has_weighted_disagreement(fake_voters, authentic_voters):
        return round(final_score, 4), "needs_review"

    raw_verdict = _band(final_score)

    if (
        raw_verdict in ("fake", "likely_fake")
        and len(fake_voters) < MIN_CORROBORATING_FOR_FAKE
        and not _single_dominant_fake_voter(fake_voters, authentic_voters, prob_scores)
    ):
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
