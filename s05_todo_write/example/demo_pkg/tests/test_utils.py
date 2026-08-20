"""Unit tests for demo_pkg.utils."""

from demo_pkg.utils import add, multiply


def test_add() -> None:
    """Test that add returns the sum of its arguments."""
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0


def test_multiply() -> None:
    """Test that multiply returns the product of its arguments."""
    assert multiply(2, 3) == 6
    assert multiply(-2, 3) == -6
    assert multiply(0, 5) == 0
