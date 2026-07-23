from app.rag.embeddings import embedding_model
from app.rag.store import cosine_similarity


def test_real_embedding_model_produces_normalized_vectors():
    vectors = embedding_model.embed(["the gas detector alarm threshold is 10 percent LEL"])
    assert len(vectors) == 1
    norm_sq = sum(v * v for v in vectors[0])
    assert abs(norm_sq - 1.0) < 1e-4  # normalize_embeddings=True -> unit vectors


def test_semantically_similar_sentences_score_higher_than_unrelated_ones():
    query = "what should I do if a valve gasket is leaking"
    similar = "procedure for handling a seal failure on a process valve"
    unrelated = "the quarterly staff cafeteria menu has been updated"

    vectors = embedding_model.embed([query, similar, unrelated])
    sim_to_similar = cosine_similarity(vectors[0], vectors[1])
    sim_to_unrelated = cosine_similarity(vectors[0], vectors[2])

    assert sim_to_similar > sim_to_unrelated
