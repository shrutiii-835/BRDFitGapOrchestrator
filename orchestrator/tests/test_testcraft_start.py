"""Starting a run at TestCraft; no platform calls are made."""

import uuid
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from temporalio.exceptions import CancelledError, ChildWorkflowError

# testcraft_artifacts is aliased: pytest collects any module-level name starting with
# "test" as a test, and would try to run it as one.
from src.agent.testcraft import (
    build_testcraft_payload,
    validate_testcraft_result,
)
from src.agent.testcraft import testcraft_artifacts as artifacts_of

agent_module = import_module("src.agent.agent")

TESTCRAFT_UUID = uuid.UUID("00000000-0000-4000-8000-00000000c7a5")
FITGAP_KEY = "synthetic-output/fitgap.xlsx"
WORKBOOK = {
    "type": "s3_download_link",
    "title": "Test Scenarios and Scripts",
    "file_key": "synthetic-output/tests.xlsx",
    "label": "Download Excel",
    "extension": "xlsx",
}


def child_error():
    return ChildWorkflowError(
        "sensitive internal error",
        namespace="synthetic",
        workflow_id="child",
        run_id="run",
        workflow_type="TestCraft",
        initiated_event_id=1,
        started_event_id=2,
        retry_state=None,
    )


@pytest.fixture
def testcraft_result():
    return {
        "status": "success",
        "message": "Test scenarios and scripts generated successfully.",
        "test_cases_document": dict(WORKBOOK),
        "results": [dict(WORKBOOK)],
    }


@pytest.fixture
def execute(monkeypatch, testcraft_result):
    call = AsyncMock(return_value=testcraft_result)
    monkeypatch.setattr(agent_module.agentExecutor, "execute", call)
    monkeypatch.setattr(agent_module.workflow, "uuid4", lambda: TESTCRAFT_UUID)
    monkeypatch.setattr(
        agent_module.workflow, "info", lambda: SimpleNamespace(workflow_id="root-test")
    )
    monkeypatch.setattr(agent_module.humanInput, "request", AsyncMock())
    return call


# --- the payload TestCraft is handed -----------------------------------------------


def test_testcraft_is_started_and_collects_its_own_files():
    """No file given: TestCraft opens its own upload box, as BRDGen does."""
    assert build_testcraft_payload(None) == {"generate": True}


def test_a_usable_document_is_forwarded_so_it_is_not_asked_for_twice():
    assert build_testcraft_payload(FITGAP_KEY) == {"generate": True, "uploaded_files": [FITGAP_KEY]}


@pytest.mark.parametrize(
    "key",
    [
        "synthetic-output/report.pdf",  # TestCraft takes no PDF
        "https://example.com/fitgap.xlsx",
        "/tmp/fitgap.xlsx",
        "../fitgap.xlsx",
        "fitgap",
        "",
        None,
        17,
    ],
)
def test_a_document_testcraft_cannot_use_is_never_forwarded(key):
    """Better its own upload box than a key it will fail to read."""
    assert build_testcraft_payload(key) == {"generate": True}


@pytest.mark.parametrize("extension", [".xlsx", ".docx", ".txt", ".md"])
def test_every_type_testcraft_accepts_is_forwarded(extension):
    key = f"synthetic-output/fitgap{extension}"
    assert build_testcraft_payload(key)["uploaded_files"] == [key]


async def test_platform_context_is_not_sent_because_testcraft_reads_none(execute):
    await agent_module.orchestrator.fn(
        {
            "start_workflow": True,
            "start_from": "TestCraft",
            "task_metadata": {"conversation_id": "c"},
            "customer_id": "t",
            "user_id": "u",
        }
    )
    child_payload = execute.await_args.args[1]
    for absent in ("task_metadata", "customer_id", "user_id"):
        assert absent not in child_payload


# --- what comes back ----------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "done",
        {"status": "finished"},
        {"status": "error"},
        {},
        {"status": "success", "results": "a workbook"},
        {"status": "success", "results": [["not a dict"]]},
        {"status": "success", "results": [{"file_key": "../escape.xlsx"}]},
        {"status": "success", "test_cases_document": "tests.xlsx"},
        {"status": "success", "test_cases_document": {"file_key": "/tmp/tests.xlsx"}},
    ],
)
def test_an_unusable_result_is_refused(bad):
    with pytest.raises(ValueError):
        validate_testcraft_result(bad)


def test_success_without_a_workbook_is_refused():
    """Never report a document the user cannot download."""
    with pytest.raises(ValueError, match="without a workbook"):
        validate_testcraft_result({"status": "success", "results": []})


def test_a_cancelled_run_needs_no_workbook(testcraft_result):
    stopped = {"status": "cancelled", "reason": "Rejected at the scenarios review."}
    assert validate_testcraft_result(stopped) == stopped


def test_artifacts_prefer_the_results_list(testcraft_result):
    assert artifacts_of(testcraft_result) == testcraft_result["results"]


def test_artifacts_fall_back_to_the_flat_workbook():
    assert artifacts_of({"status": "success", "test_cases_document": WORKBOOK}) == [WORKBOOK]


def test_artifacts_are_empty_when_there_is_nothing_to_show():
    assert artifacts_of({"status": "cancelled", "reason": "stopped"}) == []


# --- the run itself -----------------------------------------------------------------


async def test_testcraft_runs_under_an_id_the_orchestrator_owns(execute, testcraft_result):
    result = await agent_module.orchestrator.fn(
        {"start_workflow": True, "start_from": "TestCraft", "brd_file": FITGAP_KEY}
    )
    execute.assert_awaited_once()
    name, child_payload = execute.await_args.args
    assert name == "TestCraft"
    assert child_payload == {"generate": True, "uploaded_files": [FITGAP_KEY]}
    assert execute.await_args.kwargs["workflow_id"] == str(TESTCRAFT_UUID)
    assert execute.await_args.kwargs["execution_timeout"].days == 2
    assert execute.await_args.kwargs["retry_policy"].maximum_attempts == 1
    assert result["status"] == "success"
    assert result["stage"] == "testcraft"
    assert result["start_from"] == "TestCraft"
    assert result["testcraft_workflow_id"] == str(TESTCRAFT_UUID)
    assert result["test_cases_document"] == WORKBOOK
    assert WORKBOOK in result["artifacts"]


async def test_no_earlier_stage_is_run_or_reported(execute):
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "TestCraft"})
    assert execute.await_count == 1
    assert execute.await_args.args[0] == "TestCraft"
    for absent in ("brd_workflow_id", "fitmap_workflow_id", "continue_decision"):
        assert absent not in result


async def test_a_failed_run_is_named_rather_than_explained_away(execute):
    execute.side_effect = child_error()
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "TestCraft"})
    assert result["status"] == "error"
    assert result["stage"] == "testcraft"
    assert result["testcraft_workflow_id"] == str(TESTCRAFT_UUID)
    assert "TestCraft could not complete" in result["message"]
    # The child's own failure text is never shown to the user.
    assert "sensitive internal error" not in result["message"]


async def test_cancellation_is_not_converted_to_a_generic_failure(execute):
    error = child_error()
    error.__cause__ = CancelledError("cancelled")
    execute.side_effect = error
    with pytest.raises(ChildWorkflowError):
        await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "TestCraft"})


async def test_an_unrecognised_result_stops_rather_than_reporting_success(execute):
    execute.return_value = {"status": "finished"}
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "TestCraft"})
    assert result["status"] == "error"
    assert result["stage"] == "testcraft"
    assert "unrecognized result" in result["message"]


async def test_a_stopped_run_reports_its_own_reason(execute):
    execute.return_value = {"status": "cancelled", "reason": "Rejected at the scripts review."}
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "TestCraft"})
    assert result["status"] == "cancelled"
    assert result["message"] == "Rejected at the scripts review."
    assert result["artifacts"][0]["text"] == "Rejected at the scripts review."


async def test_the_result_is_a_copy_so_testcraft_s_own_dict_is_untouched(execute, testcraft_result):
    before = {k: v for k, v in testcraft_result.items()}
    await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "TestCraft"})
    assert testcraft_result == before
