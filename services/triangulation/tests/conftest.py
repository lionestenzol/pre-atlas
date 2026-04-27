from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


ElementFactory = Callable[
    [str, str, tuple[float, float, float, float], str | None, str, str],
    dict,
]
LargePageFactory = Callable[[int], list[dict]]


@pytest.fixture
def make_element() -> ElementFactory:
    def _make_element(
        id: str,
        label: str,
        bbox: tuple[float, float, float, float],
        parent_id: str | None = None,
        screenshot_path: str = "/x.png",
        page_id: str = "p1",
    ) -> dict:
        return {
            "id": id,
            "label": label,
            "bbox": bbox,
            "parent_id": parent_id,
            "screenshot_path": screenshot_path,
            "page_id": page_id,
        }

    return _make_element


@pytest.fixture
def nav_row(make_element: ElementFactory) -> list[dict]:
    return [
        make_element(f"nav-{index}", "nav_link", (10 + (index * 100), 10, 80, 24))
        for index in range(5)
    ]


@pytest.fixture
def nav_row_with_outlier(make_element: ElementFactory) -> list[dict]:
    row = [
        make_element(f"nav-{index}", "nav_link", (10 + (index * 100), 10, 80, 24))
        for index in range(5)
    ]
    row[4] = make_element("nav-4", "button", (410, 10, 80, 24))
    return row


@pytest.fixture
def pricing_grid(make_element: ElementFactory) -> list[dict]:
    grid: list[dict] = []
    for row in range(3):
        for col in range(3):
            grid.append(
                make_element(
                    f"card-{row}-{col}",
                    "pricing_card",
                    (20 + (col * 220), 40 + (row * 180), 180, 140),
                )
            )
    return grid


@pytest.fixture
def lonely_element(make_element: ElementFactory) -> dict:
    return make_element("solo-1", "hero_title", (50, 50, 240, 48))


@pytest.fixture
def large_page(make_element: ElementFactory) -> LargePageFactory:
    def _large_page(n: int = 1000) -> list[dict]:
        return [
            make_element(
                id=f"el-{index}",
                label="tile",
                bbox=((index % 50) * 30, (index // 50) * 30, 20, 20),
            )
            for index in range(n)
        ]

    return _large_page

