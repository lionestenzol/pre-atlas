import pytest

from workflow_log import init_log_db, log_execution, get_logs, run_with_recovery


@pytest.fixture
def conn():
    return init_log_db()


def test_log_execution_records_row(conn):
    log_execution(conn, "content_automation", "success")
    logs = get_logs(conn, "content_automation")
    assert logs == [{"workflow_name": "content_automation", "status": "success", "error_message": ""}]


def test_run_with_recovery_success_path(conn):
    result = run_with_recovery(conn, "content_automation", lambda: None)
    assert result is True
    logs = get_logs(conn, "content_automation")
    assert logs[0]["status"] == "success"


def test_run_with_recovery_failure_calls_recovery(conn):
    recovered = []

    def failing():
        raise RuntimeError("api down")

    def recover():
        recovered.append(True)

    result = run_with_recovery(conn, "sales_automation", failing, recover)

    assert result is False
    assert recovered == [True]

    main_log = get_logs(conn, "sales_automation")
    assert main_log[0]["status"] == "failed"
    assert "api down" in main_log[0]["error_message"]

    recovery_log = get_logs(conn, "sales_automation:recovery")
    assert recovery_log[0]["status"] == "success"


def test_run_with_recovery_logs_when_recovery_also_fails(conn):
    def failing():
        raise RuntimeError("api down")

    def failing_recovery():
        raise RuntimeError("recovery unreachable")

    run_with_recovery(conn, "sales_automation", failing, failing_recovery)

    recovery_log = get_logs(conn, "sales_automation:recovery")
    assert recovery_log[0]["status"] == "failed"
    assert "recovery unreachable" in recovery_log[0]["error_message"]


def test_run_with_recovery_no_recovery_func_given(conn):
    def failing():
        raise RuntimeError("boom")

    result = run_with_recovery(conn, "job", failing)
    assert result is False
    assert get_logs(conn, "job:recovery") == []
