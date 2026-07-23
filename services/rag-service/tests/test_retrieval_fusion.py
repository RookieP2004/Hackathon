from app.rag.retrieval import reciprocal_rank_fusion


def test_item_ranked_first_everywhere_scores_highest():
    rankings = [["a", "b", "c"], ["a", "c", "b"], ["a", "b", "c"]]
    scores = reciprocal_rank_fusion(rankings)
    assert max(scores, key=scores.get) == "a"


def test_item_appearing_in_more_signals_outranks_single_signal_hit():
    # "b" appears near the top of two signals; "z" appears only once, ranked first in the smallest signal.
    rankings = [["b", "x", "y"], ["b", "y", "x"], ["z"]]
    scores = reciprocal_rank_fusion(rankings)
    assert scores["b"] > scores["z"]


def test_absent_from_all_rankings_gets_no_score():
    rankings = [["a", "b"], ["a"]]
    scores = reciprocal_rank_fusion(rankings)
    assert "never_ranked" not in scores


def test_empty_rankings_produce_empty_scores():
    assert reciprocal_rank_fusion([[], [], []]) == {}
