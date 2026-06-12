"""Regression / golden tests: headline results are stable and deterministic.

These guard against unintended metric drift — if a refactor changes a published
number, the golden assertion flips red. Tolerances are tight because the pipeline
is fully deterministic.
"""

from src.evaluation import noise_scaling_experiment, run_full_eval
from src.manuscript_variables import generate_variables

GOLDEN_COMPOSITE = 0.621
GOLDEN_GROUNDING = 0.830
GOLDEN_EFFICIENCY = 0.854
TOL = 0.02


class TestGoldenMetrics:
    def test_composite_stable(self):
        assert abs(run_full_eval()["composite"] - GOLDEN_COMPOSITE) < TOL

    def test_grounding_stable(self):
        assert abs(run_full_eval()["grounding"] - GOLDEN_GROUNDING) < TOL

    def test_efficiency_stable(self):
        assert abs(run_full_eval()["efficiency"] - GOLDEN_EFFICIENCY) < TOL

    def test_n_examples(self):
        assert run_full_eval()["n_examples"] == 6


class TestTokenStability:
    def test_published_tokens(self):
        variables = generate_variables()
        assert variables["RESULT_COMPOSITE"] == "0.621"
        assert variables["RESULT_NUM_EXAMPLES"] == "6"
        assert variables["CONFIG_NUM_STAGES"] == "5"


class TestDeterminism:
    def test_full_eval_byte_identical(self):
        assert run_full_eval() == run_full_eval()

    def test_variables_identical(self):
        assert generate_variables() == generate_variables()


class TestNoiseRegime:
    """Pin the noise-regime ordering the §evaluation prose now cites.

    Anti-recurrence gate for the claim-verification finding that §evaluation
    previously said the hashing "semantic" lane "tracks the lexical lane" and
    that "the hybrid lane never underperforms the stronger lane" — both refuted
    by the noise-scaling data, where the surrogate semantic lane scores *above*
    lexical/hybrid at every distractor level. Making the true ordering a
    red-on-drift assertion keeps prose and data bound together.
    """

    def test_semantic_beats_lexical_at_every_level(self):
        # Robustness, not a cherry-picked operating point: the surrogate semantic
        # lane scores strictly above the lexical lane at *every* distractor level,
        # so the §evaluation claim is not locally true at one noise setting.
        noise = noise_scaling_experiment()
        per_level = list(zip(noise["lexical"], noise["semantic"]))
        assert per_level, "noise experiment produced no levels"
        for (lvl_l, lex), (lvl_s, sem) in per_level:
            assert lvl_l == lvl_s
            assert sem > lex, f"semantic !> lexical at {lvl_l} distractors: {sem} vs {lex}"

    def test_hybrid_equals_lexical_under_noise(self):
        # The hybrid lane is byte-identical to the lexical lane on this probe, so
        # it underperforms the stronger (semantic) lane. This equality is NOT a
        # dead semantic weight: ``test_fusion.py::test_weights_change_winner``
        # proves the lane weights change the fused winner, and the
        # ``rrf_agreement_boost`` invariant proves both lanes are consumed. It is
        # an emergent property of *this* dataset — the gold window is rank-0 in
        # both lanes, so the weighted top-k coincides with lexical's. Pinning the
        # identity catches a silent relabel of the hybrid array.
        noise = noise_scaling_experiment()
        assert noise["hybrid"] == noise["lexical"]
        assert noise["hybrid"][-1][1] < noise["semantic"][-1][1]

    def test_noise_tokens_match_data(self):
        noise = noise_scaling_experiment()
        variables = generate_variables()
        assert variables["RESULT_NOISE_LEXICAL"] == f"{noise['lexical'][-1][1]:.3f}"
        assert variables["RESULT_NOISE_SEMANTIC"] == f"{noise['semantic'][-1][1]:.3f}"
        assert variables["RESULT_NOISE_MAX_DISTRACTORS"] == str(noise["lexical"][-1][0])
        assert float(variables["RESULT_NOISE_SEMANTIC"]) > float(variables["RESULT_NOISE_LEXICAL"])
