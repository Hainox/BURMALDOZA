import pytest
from burmaldoza_domain.rng import SeededRandomSource


def test_seeded_source_is_reproducible() -> None:
    first = SeededRandomSource(42)
    second = SeededRandomSource(42)

    assert [first.randbelow(100) for _ in range(8)] == [
        second.randbelow(100) for _ in range(8)
    ]


def test_randbelow_rejects_non_positive_upper_bound() -> None:
    source = SeededRandomSource(42)

    with pytest.raises(ValueError):
        source.randbelow(0)


def test_randbelow_stays_inside_upper_bound() -> None:
    source = SeededRandomSource(42)

    values = [source.randbelow(7) for _ in range(100)]

    assert all(0 <= value < 7 for value in values)
