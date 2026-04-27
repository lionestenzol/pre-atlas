"""Shared pytest fixtures for the perception test suite."""

from __future__ import annotations

import pytest

from perception.schema import Element, ElementType


@pytest.fixture
def sample_element() -> Element:
    return Element(
        id="e1",
        type=ElementType.NAV,
        label="primary nav",
        x=0.0,
        y=0.0,
        w=100.0,
        h=8.0,
    )
