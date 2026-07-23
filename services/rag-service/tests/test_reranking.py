from app.rag.reranking import cross_encoder


def test_real_cross_encoder_ranks_relevant_text_above_irrelevant():
    query = "what is the inspection interval for fire suppression systems"
    relevant = "fixed fire suppression systems shall be inspected at intervals not exceeding 180 days"
    irrelevant = "the cafeteria will be closed for renovation next week"

    scores = cross_encoder.score(query, [relevant, irrelevant])
    assert scores[0] > scores[1]
