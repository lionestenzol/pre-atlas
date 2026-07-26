"""Quiz grader — port of conversation #363 "Quiz Template Creation"
(2025-02-23), Pre Atlas harvest pipeline.

The source thread's real deliverable (its very first user message was
"generate a template for a quiz") is a JSON quiz schema supporting four
question types -- multiple_choice, true_false, short_answer, numeric --
where `correct_answer` can be a string, a number, or a dict (e.g. a
coordinate pair for a graph-reading question). The source never went
past the schema examples; this adds the grader that actually consumes
it, since a quiz template with nothing to score answers against isn't
a usable deliverable.
"""


def grade_quiz(quiz, answers):
    """Grade `answers` (question_number -> submitted answer) against `quiz`.

    Returns a dict with per-question results and a total score, using
    the quiz's own `scoring` block for point values.
    """
    scoring = quiz.get("scoring", {"correct": 1, "incorrect": 0, "partial_credit": False})
    results = []
    total = 0

    for question in quiz["questions"]:
        qnum = question["question_number"]
        submitted = answers.get(qnum)
        correct = _answer_matches(question["correct_answer"], submitted)
        points = scoring["correct"] if correct else scoring["incorrect"]
        total += points
        results.append({
            "question_number": qnum,
            "correct": correct,
            "points": points,
            "submitted": submitted,
            "explanation": question.get("explanation"),
        })

    return {"results": results, "total_score": total, "max_score": len(quiz["questions"]) * scoring["correct"]}


def _answer_matches(correct_answer, submitted):
    if submitted is None:
        return False
    if isinstance(correct_answer, str):
        return str(submitted).strip().lower() == correct_answer.strip().lower()
    return submitted == correct_answer
