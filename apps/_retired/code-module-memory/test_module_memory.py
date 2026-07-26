import pytest

from module_memory import save_module, load_module, list_modules


def test_save_and_load_round_trip(tmp_path):
    path = str(tmp_path / "memory.json")
    source = "<?php\necho 'hello';\n"

    save_module(path, "auth_system", source)

    assert load_module(path, "auth_system") == source


def test_list_modules_returns_names(tmp_path):
    path = str(tmp_path / "memory.json")
    save_module(path, "auth_system", "code a")
    save_module(path, "billing", "code b")

    assert sorted(list_modules(path)) == ["auth_system", "billing"]


def test_load_missing_module_raises(tmp_path):
    path = str(tmp_path / "memory.json")
    save_module(path, "auth_system", "code a")

    with pytest.raises(KeyError):
        load_module(path, "nonexistent")


def test_save_overwrites_existing_module(tmp_path):
    path = str(tmp_path / "memory.json")
    save_module(path, "auth_system", "v1")
    save_module(path, "auth_system", "v2")

    assert load_module(path, "auth_system") == "v2"
    assert list_modules(path) == ["auth_system"]


def test_load_module_from_nonexistent_file_raises(tmp_path):
    path = str(tmp_path / "does_not_exist.json")
    with pytest.raises(KeyError):
        load_module(path, "anything")
