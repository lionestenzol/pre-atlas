"""Tests for the loop scoring formula used by loops.py.

The scoring formula: score = user_words + intent_w * 30 - done_w * 50
Only loops with score >= MIN_LOOP_SCORE (18000) count as open loops.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from atlas_config import ROUTING

MIN_LOOP_SCORE = ROUTING["min_loop_score"]

# Import the topic sets from loops.py source
INTENT_TOPICS = set("want need should plan going gonna start try trying build create make learn begin".split())
DONE_TOPICS = set("did done finished completed solved shipped fixed achieved".split())


def compute_score(user_words: int, intent_weight: int, done_weight: int) -> int:
    """Replicate the loop scoring formula from loops.py."""
    return user_words + intent_weight * 30 - done_weight * 50


class TestLoopScoring:
    """Test the loop scoring formula."""

    def test_basic_score(self):
        """Simple case: only user words, no intent/done."""
        assert compute_score(20000, 0, 0) == 20000

    def test_intent_boosts_score(self):
        """Intent topics increase score by weight * 30."""
        base = compute_score(15000, 0, 0)
        boosted = compute_score(15000, 200, 0)
        assert boosted == base + 200 * 30
        assert boosted == 21000

    def test_done_reduces_score(self):
        """Done topics decrease score by weight * 50."""
        base = compute_score(20000, 0, 0)
        reduced = compute_score(20000, 0, 100)
        assert reduced == base - 100 * 50
        assert reduced == 15000

    def test_intent_and_done_combined(self):
        """Both intent and done affect score."""
        score = compute_score(18000, 100, 50)
        assert score == 18000 + 100 * 30 - 50 * 50
        assert score == 18500

    def test_score_can_go_negative(self):
        """High done weight can push score negative."""
        score = compute_score(1000, 0, 500)
        assert score == 1000 - 25000
        assert score < 0

    def test_min_loop_score_threshold(self):
        """Only scores >= 18000 count as open loops."""
        assert MIN_LOOP_SCORE == 18000
        assert compute_score(18000, 0, 0) >= MIN_LOOP_SCORE
        assert compute_score(17999, 0, 0) < MIN_LOOP_SCORE

    def test_borderline_with_intent(self):
        """Intent can push a conversation above the threshold."""
        base = compute_score(17000, 0, 0)
        assert base < MIN_LOOP_SCORE
        boosted = compute_score(17000, 40, 0)
        assert boosted == 18200
        assert boosted >= MIN_LOOP_SCORE

    def test_done_can_close_loop(self):
        """Done topics can push an open loop below threshold."""
        open_score = compute_score(20000, 100, 0)
        assert open_score >= MIN_LOOP_SCORE
        closed_score = compute_score(20000, 100, 200)
        assert closed_score == 20000 + 3000 - 10000
        assert closed_score == 13000
        assert closed_score < MIN_LOOP_SCORE


class TestTopicSets:
    """Verify intent and done topic lists are correct."""

    def test_intent_topics_not_empty(self):
        assert len(INTENT_TOPICS) > 0

    def test_done_topics_not_empty(self):
        assert len(DONE_TOPICS) > 0

    def test_no_overlap(self):
        """Intent and done topics should not overlap."""
        overlap = INTENT_TOPICS & DONE_TOPICS
        assert len(overlap) == 0, f"Overlapping topics: {overlap}"

    def test_key_intent_topics(self):
        """Key intent words are present."""
        for word in ["want", "need", "plan", "build", "create"]:
            assert word in INTENT_TOPICS

    def test_key_done_topics(self):
        """Key done words are present."""
        for word in ["done", "finished", "shipped", "completed"]:
            assert word in DONE_TOPICS
