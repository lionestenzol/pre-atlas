import pytest

from quiz_grader import grade_quiz

QUIZ = {
    "quiz_title": "Sample Quiz",
    "questions": [
        {
            "question_number": 1,
            "question_type": "multiple_choice",
            "question_text": "What is the capital of France?",
            "choices": ["Berlin", "Madrid", "Paris", "Rome"],
            "correct_answer": "Paris",
            "explanation": "Paris is the capital city of France.",
        },
        {
            "question_number": 2,
            "question_type": "true_false",
            "question_text": "The Earth is flat.",
            "choices": ["True", "False"],
            "correct_answer": "False",
            "explanation": "The Earth is an oblate spheroid.",
        },
        {
            "question_number": 3,
            "question_type": "numeric",
            "question_text": "What is the square root of 144?",
            "correct_answer": 12,
            "explanation": "12 * 12 = 144.",
        },
        {
            "question_number": 4,
            "question_type": "numeric",
            "question_text": "What is the vertex of the parabola?",
            "correct_answer": {"x": -2, "y": 4},
            "explanation": "Vertex found via -b/2a.",
        },
    ],
    "scoring": {"correct": 1, "incorrect": 0, "partial_credit": False},
}


def test_all_correct():
    answers = {1: "Paris", 2: "False", 3: 12, 4: {"x": -2, "y": 4}}
    result = grade_quiz(QUIZ, answers)
    assert result["total_score"] == 4
    assert result["max_score"] == 4
    assert all(r["correct"] for r in result["results"])


def test_string_answer_is_case_and_whitespace_insensitive():
    answers = {1: "  paris  ", 2: "false", 3: 12, 4: {"x": -2, "y": 4}}
    result = grade_quiz(QUIZ, answers)
    assert result["total_score"] == 4


def test_wrong_answers_score_zero_for_that_question():
    answers = {1: "Berlin", 2: "False", 3: 12, 4: {"x": -2, "y": 4}}
    result = grade_quiz(QUIZ, answers)
    assert result["results"][0]["correct"] is False
    assert result["total_score"] == 3


def test_missing_answer_counts_as_incorrect():
    answers = {1: "Paris"}
    result = grade_quiz(QUIZ, answers)
    incorrect = [r for r in result["results"] if not r["correct"]]
    assert len(incorrect) == 3


def test_dict_answer_requires_exact_match():
    answers = {1: "Paris", 2: "False", 3: 12, 4: {"x": -2, "y": 5}}
    result = grade_quiz(QUIZ, answers)
    assert result["results"][3]["correct"] is False
