from analyzers.management.commands.eval_detectors import _auc, _generator_of, prob_scores_for


class TestGeneratorParsing:
    def test_prefix_before_double_underscore(self):
        assert _generator_of("/x/ai_generated/flux.1-dev__001.png") == "flux.1-dev"

    def test_real_prefix(self):
        assert _generator_of("/x/real/real__0007.png") == "real"

    def test_no_separator_means_unknown(self):
        assert _generator_of("/x/ai_generated/diffusiondb_001_abc.jpg") == ""

    def test_only_first_separator_counts(self):
        assert _generator_of("gpt-image-1__extra__003.png") == "gpt-image-1"


class TestAuc:
    def test_perfect_separation(self):
        assert _auc([0.1, 0.2, 0.9, 0.8], [0, 0, 1, 1]) == 1.0

    def test_inverted_separation(self):
        assert _auc([0.9, 0.8, 0.1, 0.2], [0, 0, 1, 1]) == 0.0

    def test_ties_score_half(self):
        assert _auc([0.5, 0.5, 0.5, 0.5], [0, 0, 1, 1]) == 0.5

    def test_single_class_is_undefined(self):
        assert _auc([0.1, 0.9], [1, 1]) is None


class TestProbScoresFor:
    class _R:
        def __init__(self, evidence):
            self.evidence = evidence

    def test_prefers_ai_probability(self):
        assert prob_scores_for(self._R({"ai_probability": 0.7, "ai_probability_avg": 0.2})) == 0.7

    def test_falls_back_to_average(self):
        assert prob_scores_for(self._R({"ai_probability_avg": 0.2})) == 0.2

    def test_none_when_absent(self):
        assert prob_scores_for(self._R({})) is None
        assert prob_scores_for(self._R(None)) is None
