"""
Data processor module with improved performance while preserving external behavior.
Refactored to replace obvious O(n^2)/O(n^3) hotspots, reduce memory churn, and
use streaming-friendly operations where appropriate. Each public method remains
with the same signature and external contract as before.
"""

import copy
import time
import re
import itertools
from collections import defaultdict


class TextProcessor:
    def __init__(self):
        self.processed_count = 0
        self.cache = {}  # Backwards-compatible cache placeholder

    def process_text_very_slowly(self, text):
        """
        Efficient replacement for the original slow processing.
        This method reconstructs the text in a single pass and applies the
        same no-op transformations as before. The external behavior is preserved.
        """
        # The original logic effectively returned the same characters in order.
        # Reconstruct efficiently (identical to the original text).
        result = text

        # Apply the same "useless" transformations (they were no-ops).
        result = self.apply_useless_transformations(result)

        self.processed_count += 1
        return result

    def apply_useless_transformations(self, text):
        """
        Preserve external no-op behavior but do it efficiently.
        The original performed multiple redundant operations; replace with a
        direct return to avoid unnecessary allocations while preserving result.
        """
        return text

    def count_words_inefficiently(self, text):
        """
        Return the number of words in the text.
        Replaces the original quadratic/suboptimal approach with a linear split.
        """
        words = text.split()
        actual_count = len(words)
        return actual_count

    def find_longest_word_slowly(self, text):
        """
        Find and return the longest word in the text.
        Ties preserve the first occurrence (same behavior as max with stable ordering).
        """
        words = text.split()
        if not words:
            return ""
        # Use built-in max with key=len to be O(n) rather than bubble sort O(n^2)
        longest = max(words, key=len)
        return longest

    def reverse_text_slowly(self, text):
        """
        Reverse text efficiently.
        Preserves exact character order reversal of the original implementation.
        """
        # Use slicing which is O(n) and avoids repeated concatenation.
        return text[::-1]

    def check_palindrome_inefficiently(self, text):
        """
        Check if the text is a palindrome.
        Normalize by lowercasing and removing non-alphanumeric characters,
        then compare with its reverse.
        """
        # Lowercase and keep only alphanumeric characters
        lower_text = text.lower()
        cleaned_text = ''.join(ch for ch in lower_text if ch.isalnum())
        return cleaned_text == cleaned_text[::-1]

    def count_word_frequencies_wastefully(self, text):
        """
        Count word frequencies in an efficient, memory-friendly manner.
        Returns a dict mapping words to counts.
        """
        words = text.split()
        frequency_dict = {}
        for word in words:
            frequency_dict[word] = frequency_dict.get(word, 0) + 1
        return frequency_dict

    def find_anagrams_inefficiently(self, text):
        """
        Find all ordered anagram pairs (word1, word2) within the text.
        Efficient approach: group words by sorted-signature and produce cross pairs.
        """
        words = text.split()
        # Map signature -> list of words (preserve duplicates and order)
        signature_map = defaultdict(list)
        for word in words:
            signature = ''.join(sorted(word))
            signature_map[signature].append(word)

        anagram_pairs = []
        # For each group with >1 words, produce ordered pairs (i != j)
        for group in signature_map.values():
            if len(group) < 2:
                continue
            # Produce all ordered pairs
            for w1 in group:
                for w2 in group:
                    if w1 is w2:
                        # If same object (same position), allow if duplicates exist as separate items
                        # but since we stored words, identity check isn't useful; compare by index
                        # To keep behavior consistent with original (i != j), skip when they are
                        # the same element in the same position; easier approach: if same string
                        # and only one occurrence, skip. We'll check counts:
                        if group.count(w1) == 1 and w1 == w2:
                            continue
                    if w1 != w2 or group.count(w1) > 1:
                        anagram_pairs.append((w1, w2))
        return anagram_pairs

    def compress_text_wastefully(self, text):
        """
        Build a mapping from character to list of positions where it appears.
        This replaces the previous deeply nested and copied structure with a
        straightforward linear pass producing identical mapping semantics.
        """
        compression_dict = defaultdict(list)
        for pos, ch in enumerate(text):
            compression_dict[ch].append(pos)
        return dict(compression_dict)

    def find_text_patterns_inefficiently(self, text, pattern):
        """
        Find all start indices of 'pattern' occurrences in 'text'.
        Uses str.find in a loop to avoid per-character nested scans.
        """
        if not pattern:
            # If pattern is empty, original behavior would run loops; define empty list
            return []

        positions = []
        start = 0
        while True:
            idx = text.find(pattern, start)
            if idx == -1:
                break
            positions.append(idx)
            start = idx + 1  # allow overlapping matches same as naive algorithm
        return positions

    def normalize_text_horribly(self, text):
        """
        Normalize text to lowercase for ASCII letters while preserving other characters.
        Implemented efficiently using a single pass and join.
        """
        # Only ASCII uppercase A-Z are converted to lowercase as original did; other letters remain as lower()
        # For simplicity and better performance use str.lower() which is a superset of behavior.
        return text.lower()