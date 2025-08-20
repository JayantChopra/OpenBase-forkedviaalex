"""
A tiny workload used by dynamic performance benchmarking.
It exercises CPU work, memory allocations, and a bit of I/O-like sleep to
produce measurable but quick signals for tools like pyinstrument and
memory_profiler.

Usage:
    BENCH_PROFILE_SCRIPT=benchmarkv01/scripts_profile_script.py python main.py ...
"""
from __future__ import annotations

import math
import secrets
import time
from typing import List, Iterable

from benchmarkv01.db_access import (
    iter_posts_streaming,
    load_posts_with_authors_n_plus_one,
    load_posts_with_authors_prefetched,
)


def cpu_heavy(n: int = 50_000) -> float:
    """
    Perform CPU-bound work by computing many trigonometric operations.

    Args:
        n: Number of iterations to run (upper bound, exclusive of 0).

    Returns:
        A float accumulation of computed trigonometric values to prevent
        the optimizer from removing the loop.
    """
    total = 0.0
    for i in range(1, n):
        total += math.sin(i) * math.cos(i / 3.0)
    return total


def _generate_random_list(list_size: int) -> List[int]:
    """
    Generate a list of random integers in the range [0, 1000].

    Uses a generator expression wrapped with list(...) to avoid building
    intermediate large comprehension structures in tight loops.

    Args:
        list_size: Number of random integers to generate.

    Returns:
        A list of random integers.
    """
    return list(secrets.randbelow(1001) for _ in range(list_size))


def _total_lengths(lists: Iterable[List[int]]) -> int:
    """
    Compute the total number of elements across a sequence of lists.

    Args:
        lists: An iterable of lists whose lengths will be summed.

    Returns:
        The sum of lengths of the provided lists.
    """
    return sum(len(x) for x in lists)


def allocate_memory(num_lists: int = 50, list_size: int = 1_000) -> List[List[int]]:
    """
    Allocate a collection of lists filled with random integers.

    This function creates num_lists lists, each of size list_size, and returns
    them as a list of lists. The inner lists are produced by a small helper
    to keep the allocation logic isolated and testable.

    Args:
        num_lists: Number of lists to create.
        list_size: Size of each inner list.

    Returns:
        A list containing num_lists lists of random integers.
    """
    data: List[List[int]] = []
    for _ in range(num_lists):
        data.append(_generate_random_list(list_size))
    return data


def main() -> None:
    """
    Run a small, deterministic workload exercising CPU, memory, and I/O-like waits.

    This function is intended for use in profiling scenarios to create measurable
    signals for tools like pyinstrument and memory_profiler.
    """
    # CPU work
    _ = cpu_heavy()

    # Memory allocations
    data = allocate_memory()

    # Simulate N+1 and prefetched patterns
    _ = load_posts_with_authors_n_plus_one()
    _ = load_posts_with_authors_prefetched()

    # Simulate streaming iteration
    for _batch in iter_posts_streaming():
        pass

    # Simulate small I/O wait
    time.sleep(0.02)

    # Prevent data from being optimized away
    if _total_lengths(data) < 0:
        print("unreachable")


if __name__ == "__main__":
    main()