"""
Tests for core/symbols.py — mirrors services/delta-scp/src/compressor.test.ts
coverage so the Python port and the TS original stay provably equivalent.
"""
from __future__ import annotations

import json

from core import symbols


def test_language_for_path_maps_known_extensions():
    assert symbols.language_for_path("src/foo.ts") == "typescript"
    assert symbols.language_for_path("a/b/c.py") == "python"
    assert symbols.language_for_path("main.go") == "go"


def test_language_for_path_falls_back_to_other():
    assert symbols.language_for_path("image.png") == "other"
    assert symbols.language_for_path("NOEXT") == "other"


def test_include_file_matches_delta_scp_allowlist():
    assert symbols.include_file("index.ts") is True
    assert symbols.include_file("readme.md") is True
    assert symbols.include_file("photo.png") is False
    assert symbols.include_file("archive.zip") is False


def test_estimate_tokens_approximates_four_chars_per_token():
    assert symbols.estimate_tokens("") == 0
    assert symbols.estimate_tokens("abcd") == 1
    assert symbols.estimate_tokens("abcde") == 2


def test_extract_symbols_ts_functions_classes_interfaces_exports():
    src = "\n".join([
        "export function alpha() {}",  # 1
        "class Beta {}",  # 2
        "export const gamma = 3;",  # 3
        "interface Delta {}",  # 4
    ])
    syms = symbols.extract_symbols(src, "typescript")
    assert [(s.kind, s.name, s.line) for s in syms] == [
        ("function", "alpha", 1),
        ("class", "Beta", 2),
        ("const", "gamma", 3),
        ("interface", "Delta", 4),
    ]


def test_extract_symbols_python_def_class():
    src = "class Foo:\n    def bar(self):\n        pass\n"
    syms = symbols.extract_symbols(src, "python")
    assert [(s.kind, s.name, s.line) for s in syms] == [
        ("class", "Foo", 1),
        ("def", "bar", 2),
    ]


def test_extract_symbols_returns_nothing_for_unpatterned_language():
    assert symbols.extract_symbols("# title", "markdown") == []


def test_compress_tree_produces_deterministic_sorted_nodes(tmp_path):
    (tmp_path / "b.ts").write_text("export function b() {}\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")

    warnings: list[str] = []
    out = symbols.compress_tree(tmp_path, ["b.ts", "a.py"], warnings)

    assert [n.path for n in out.symbolic_nodes] == ["a.py", "b.ts"]
    assert [n.language for n in out.symbolic_nodes] == ["python", "typescript"]
    assert warnings == []


def test_compress_tree_is_deterministic_across_repeated_calls(tmp_path):
    (tmp_path / "b.ts").write_text("export function b() {}\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")

    first = symbols.compress_tree(tmp_path, ["b.ts", "a.py"], [])
    second = symbols.compress_tree(tmp_path, ["b.ts", "a.py"], [])
    assert first.model_dump() == second.model_dump()


def test_compress_tree_reports_positive_token_yield_on_real_source(tmp_path):
    def block(i: int) -> str:
        return (
            f"export function fn{i}(input: string): string {{\n"
            "  const trimmed = input.trim();\n"
            "  const upper = trimmed.toUpperCase();\n"
            "  // perform the transformation and return the result\n"
            "  return upper + trimmed.length.toString();\n"
            "}\n\n"
        )

    (tmp_path / "big.ts").write_text("".join(block(i) for i in range(200)), encoding="utf-8")

    out = symbols.compress_tree(tmp_path, ["big.ts"], [])
    assert out.files_included == 1
    assert out.raw_tokens_est > out.compressed_tokens_est
    assert out.token_yield == out.raw_tokens_est - out.compressed_tokens_est
    assert 0 < out.compression_ratio < 1


def test_compress_tree_handles_empty_input_without_dividing_by_zero(tmp_path):
    out = symbols.compress_tree(tmp_path, [], [])
    assert out.raw_tokens_est == 0
    assert out.compression_ratio == 0
    assert out.symbolic_nodes == []


def test_compress_tree_records_warning_for_unreadable_file(tmp_path):
    binary = tmp_path / "broken.py"
    binary.write_bytes(b"\xff\xfe\x00\xff not valid utf-8 \xff")

    warnings: list[str] = []
    out = symbols.compress_tree(tmp_path, ["broken.py"], warnings)

    assert out.symbolic_nodes == []
    assert len(warnings) == 1
    assert "broken.py" in warnings[0]
