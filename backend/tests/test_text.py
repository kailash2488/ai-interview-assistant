from app.services.interview.text import clean_question, is_duplicate, similarity


def test_similarity_and_duplicates():
    a = "How have you used FastAPI in production?"
    assert is_duplicate("How did you use FastAPI in production?", [a])
    assert not is_duplicate("Explain database indexing trade-offs.", [a])
    assert similarity("", a) == 0.0


def test_clean_question_strips_noise_and_keeps_one_question():
    assert clean_question('"Question 2: How do you test APIs?"') == "How do you test APIs?"
    assert clean_question("1. What is a decorator?") == "What is a decorator?"
    assert clean_question("What is Docker? And how is it different from a VM? Explain.") == "What is Docker?"
    assert clean_question("Tell me about caching.\n\nNote: be brief") == "Tell me about caching."
