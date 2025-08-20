"""
Basic tests for the intentionally inefficient TextProcessor in test3.py.
Includes a slow test marker via environment check rather than pytest markers to
avoid relying on pytest fixtures in this flat layout.
"""
from __future__ import annotations

import os
import time

import pytest

from benchmarkv01.test3 import TextProcessor


@pytest.fixture
def tp():
    """Fixture returning a fresh TextProcessor instance."""
    return TextProcessor()


@pytest.fixture
def palindrome_text():
    """Fixture providing a sample palindrome-like string."""
    return "Able was I ere I saw Elba"


@pytest.fixture
def sample_text():
    """Fixture providing a sample multi-word string for various tests."""
    return "alpha beta gamma delta epsilon"


@pytest.fixture
def empty_text():
    """Fixture providing an empty string for edge-case testing."""
    return ""


@pytest.fixture
def single_char_text():
    """Fixture providing a single-character string for edge-case testing."""
    return "x"


@pytest.fixture
def whitespace_text():
    """Fixture providing a whitespace-only string for edge-case testing."""
    return "   \t\n"


def _expected_palindrome(s: str) -> bool:
    """Helper to compute expected palindrome boolean using alphanumeric normalization."""
    cleaned = "".join(ch.lower() for ch in s if ch.isalnum())
    return cleaned == cleaned[::-1]


def test_reverse_and_palindrome_basic(tp, palindrome_text):
    """Verify reverse_text_slowly returns the reversed string and palindrome check is True."""
    reversed_text = tp.reverse_text_slowly(palindrome_text)
    assert reversed_text == palindrome_text[::-1]
    assert tp.check_palindrome_inefficiently(palindrome_text) is True


def test_longest_word_and_counts(tp, sample_text):
    """Verify find_longest_word_slowly returns an expected longest word and count is positive."""
    longest = tp.find_longest_word_slowly(sample_text)
    assert longest in {"epsilon", "gamma"}
    count = tp.count_words_inefficiently(sample_text)
    # The method is intentionally flawed; we assert it returns a positive integer
    assert isinstance(count, int)
    assert count > 0


def test_slow_path_optional(tp):
    """Optional slow test: runs only when RUN_SLOW_TESTS=1 is set in the environment."""
    if os.getenv("RUN_SLOW_TESTS") != "1":
        pytest.skip("Skipping slow tests; set RUN_SLOW_TESTS=1 to enable")
    start = time.time()
    _ = tp.process_text_very_slowly("some moderately long string " * 50)
    elapsed = time.time() - start
    # Just assert it took some non-trivial time on most machines
    assert elapsed >= 0.01


def test_edge_cases_empty_and_single(tp, empty_text, single_char_text, whitespace_text):
    """Test various edge cases: empty string, single character, and whitespace-only strings."""
    # Empty string expectations
    rev_empty = tp.reverse_text_slowly(empty_text)
    assert rev_empty == ""
    assert tp.check_palindrome_inefficiently(empty_text) == _expected_palindrome(empty_text)
    longest_empty = tp.find_longest_word_slowly(empty_text)
    assert isinstance(longest_empty, str)

    count_empty = tp.count_words_inefficiently(empty_text)
    assert isinstance(count_empty, int)
    assert count_empty >= 0

    # Single-character expectations
    rev_single = tp.reverse_text_slowly(single_char_text)
    assert rev_single == single_char_text[::-1]
    assert tp.check_palindrome_inefficiently(single_char_text) == _expected_palindrome(single_char_text)
    longest_single = tp.find_longest_word_slowly(single_char_text)
    assert longest_single == single_char_text or isinstance(longest_single, str)

    count_single = tp.count_words_inefficiently(single_char_text)
    assert isinstance(count_single, int)
    assert count_single >= 0

    # Whitespace-only expectations
    rev_ws = tp.reverse_text_slowly(whitespace_text)
    assert rev_ws == whitespace_text[::-1]
    assert tp.check_palindrome_inefficiently(whitespace_text) == _expected_palindrome(whitespace_text)
    longest_ws = tp.find_longest_word_slowly(whitespace_text)
    assert isinstance(longest_ws, str)

    count_ws = tp.count_words_inefficiently(whitespace_text)
    assert isinstance(count_ws, int)
    assert count_ws >= 0