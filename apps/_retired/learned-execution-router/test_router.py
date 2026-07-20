import pytest

from router import LearnedExecutionRouter


def test_execute_routes_to_registered_handler():
    router = LearnedExecutionRouter()
    router.register("PNG_1", "hashing_function", lambda: "hashed!")

    output, result = router.execute("hashing_function")

    assert output == "hashed!"
    assert result.handled_by == "PNG_1"
    assert result.forwarded_from is None


def test_execute_records_forward_when_requester_differs_from_owner():
    router = LearnedExecutionRouter()
    router.register("PNG_001", "hashing_function", lambda: "hashed!")

    output, result = router.execute("hashing_function", requesting_node="PNG_5")

    assert result.handled_by == "PNG_001"
    assert result.forwarded_from == "PNG_5"


def test_execute_unknown_task_raises():
    router = LearnedExecutionRouter()
    with pytest.raises(KeyError):
        router.execute("nonexistent_function")


def test_learn_acquires_handler_and_updates_routing():
    router = LearnedExecutionRouter()
    router.register("PNG_001", "compression_function", lambda: "compressed!")

    router.learn("PNG_1", "compression_function")

    assert router.routing_table()["compression_function"] == "PNG_1"
    output, result = router.execute("compression_function")
    assert output == "compressed!"
    assert result.handled_by == "PNG_1"


def test_learn_unknown_task_raises():
    router = LearnedExecutionRouter()
    with pytest.raises(KeyError):
        router.learn("PNG_1", "nonexistent_function")


def test_routing_table_reflects_multiple_registrations():
    router = LearnedExecutionRouter()
    router.register("PNG_001", "hashing_function", lambda: "a")
    router.register("PNG_003", "sorting_function", lambda: "b")

    table = router.routing_table()

    assert table == {"hashing_function": "PNG_001", "sorting_function": "PNG_003"}
