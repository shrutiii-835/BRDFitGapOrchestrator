"""Contract and workflow tests; actual platform calls are deliberately not made."""

import asyncio
import uuid
from copy import deepcopy
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from temporalio.exceptions import CancelledError, ChildWorkflowError

from src.agent.brd import build_brd_payload, select_brd_document, validate_brd_result

agent_module = import_module("src.agent.agent")

# Fixed so the mocked child id is assertable; the agent uses workflow.uuid4 for replay safety.
CHILD_UUID = uuid.UUID("00000000-0000-4000-8000-00000000d00d")


@pytest.fixture
def brd_result():
    return {
        "status": "success",
        "outputs": [
            {
                "type": "s3_download_link",
                "extension": "xlsx",
                "file_key": "synthetic-output/requirements.xlsx",
                "title": "BRD",
            }
        ],
    }


@pytest.fixture
def execute(monkeypatch, brd_result):
    call = AsyncMock(return_value=brd_result)
    monkeypatch.setattr(agent_module.agentExecutor, "execute", call)
    monkeypatch.setattr(
        agent_module.workflow, "info", lambda: SimpleNamespace(workflow_id="root-test")
    )
    monkeypatch.setattr(agent_module.workflow, "uuid4", lambda: CHILD_UUID)
    return call


async def test_only_brd_is_called_with_known_inputs(execute, brd_result):
    payload = {
        "start_workflow": True,
        "output_format": "Excel",
        "transcript": ["synthetic-input/meeting.txt"],
        "process_listing": ["synthetic-input/processes.xlsx"],
        "task_metadata": {"conversation_id": "synthetic-chat", "customer_id": "synthetic-tenant"},
        "agent_name": "DoNotInvoke",
        "offer_testcraft": False,
    }
    before = deepcopy(payload)
    result = await agent_module.orchestrator.fn(payload)
    execute.assert_awaited_once()
    assert execute.await_args.args == (
        "BRDGen",
        {
            "generate_brd": True,
            "output_format": "Excel",
            "transcript": payload["transcript"],
            "process_listing": payload["process_listing"],
            "task_metadata": payload["task_metadata"],
        },
    )
    assert execute.await_args.kwargs["workflow_id"] == str(CHILD_UUID)
    assert execute.await_args.kwargs["retry_policy"].maximum_attempts == 1
    assert execute.await_args.kwargs["execution_timeout"].days == 3
    assert payload == before
    assert result["status"] == "success"
    assert result["stage"] == "brd"
    assert result["outputs"] == brd_result["outputs"]
    assert result["artifacts"][1:] == brd_result["outputs"]
    assert "FitMap was not started" in result["message"]


@pytest.mark.parametrize("format_value", ["Excel", "Word", None])
async def test_requested_format_is_forwarded_only_when_present(format_value, execute):
    await agent_module.orchestrator.fn({"start_workflow": True, "output_format": format_value})
    child = execute.await_args.args[1]
    assert child.get("output_format") == format_value
    assert ("output_format" in child) == (format_value is not None)


async def test_missing_files_are_left_to_brdgen(execute):
    await agent_module.orchestrator.fn({"start_workflow": True})
    assert execute.await_args.args[1] == {"generate_brd": True}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"start_workflow": False},
        {"start_workflow": "true"},
        {"process_listing": ["meeting.txt"]},
    ],
)
async def test_no_explicit_valid_start_does_not_call_any_agent(payload, execute):
    await agent_module.orchestrator.fn(payload)
    execute.assert_not_awaited()


@pytest.mark.parametrize(
    "fields",
    [
        {"task_metadata": "bad"},
        {"transcript": "meeting.txt"},
        {"process_listing": [None]},
        {"process_listing": ["/tmp/processes.xlsx"]},
        {"transcript": ["https://example.com/file.txt"]},
        {"transcript": ["../file.txt"]},
        {"transcript": ["folder/../file.txt"]},
        {"transcript": ["C:\\file.txt"]},
        {"transcript": ["file\x00.txt"]},
    ],
)
async def test_invalid_file_or_context_input_stops_before_call(fields, execute):
    result = await agent_module.orchestrator.fn({"start_workflow": True, **fields})
    assert result["status"] == "invalid_input"
    execute.assert_not_awaited()


def test_empty_arrays_are_valid_and_payload_is_copied():
    payload = {"process_listing": [], "task_metadata": {"conversation_id": "synthetic"}}
    child = build_brd_payload(payload)
    assert child["process_listing"] == []
    assert child["process_listing"] is not payload["process_listing"]
    assert child["task_metadata"] is not payload["task_metadata"]


async def test_partial_and_consolidation_warnings_reach_chat(execute, brd_result):
    brd_result.update(
        status="partial",
        warning="One chunk failed.",
        consolidation_warning="Consolidation unavailable.",
        skipped_chunk_count=1,
    )
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    assert result["status"] == "partial"
    assert result["skipped_chunk_count"] == 1
    assert "One chunk failed." in result["artifacts"][0]["text"]
    assert "Consolidation unavailable." in result["artifacts"][0]["text"]


@pytest.mark.parametrize("status", ["cancelled", "invalid_input", "error"])
async def test_child_stop_status_and_explanation_are_preserved(status, execute):
    execute.return_value = {"status": status, "error": "Synthetic child explanation."}
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    assert result["status"] == status
    assert "Synthetic child explanation." in result["artifacts"][0]["text"]
    execute.assert_awaited_once()


@pytest.mark.parametrize(
    "result",
    [
        None,
        [],
        {},
        {"status": "unknown"},
        {"status": "success", "outputs": []},
        {"status": "success", "outputs": "bad"},
    ],
)
async def test_malformed_result_is_not_reported_as_success(result, execute):
    execute.return_value = result
    assert (await agent_module.orchestrator.fn({"start_workflow": True}))["status"] == "error"


@pytest.mark.parametrize(
    "key", ["/tmp/requirements.xlsx", "https://example.com/r.xlsx", "../r.xlsx"]
)
def test_local_or_url_output_keys_are_rejected(key, brd_result):
    brd_result["outputs"][0]["file_key"] = key
    with pytest.raises(ValueError):
        validate_brd_result(brd_result)


def test_ambiguous_documents_are_rejected(brd_result):
    brd_result["outputs"].append(deepcopy(brd_result["outputs"][0]))
    with pytest.raises(ValueError):
        validate_brd_result(brd_result)


def test_zip_alone_cannot_count_as_final_brd(brd_result):
    brd_result["outputs"][0].update(extension="zip", file_key="synthetic/data.zip")
    with pytest.raises(ValueError):
        validate_brd_result(brd_result)


def child_error():
    return ChildWorkflowError(
        "sensitive internal error",
        namespace="synthetic",
        workflow_id="child",
        run_id="run",
        workflow_type="BRDGen",
        initiated_event_id=1,
        started_event_id=2,
        retry_state=None,
    )


async def test_execution_failure_is_safe_and_not_retried(execute):
    execute.side_effect = child_error()
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    assert result["status"] == "error"
    assert "sensitive internal error" not in str(result)
    assert result["brd_workflow_id"] == str(CHILD_UUID)
    execute.assert_awaited_once()


async def test_parent_cancellation_propagates(execute):
    execute.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await agent_module.orchestrator.fn({"start_workflow": True})


async def test_child_cancellation_is_not_converted_to_generic_failure(execute):
    error = child_error()
    error.__cause__ = CancelledError("cancelled")
    execute.side_effect = error
    with pytest.raises(ChildWorkflowError):
        await agent_module.orchestrator.fn({"start_workflow": True})


async def test_word_document_and_original_zip_artifacts_are_preserved(execute, brd_result):
    brd_result["outputs"][0].update(extension="docx", file_key="synthetic/requirements.docx")
    brd_result["outputs"].append(
        {
            "type": "s3_download_link",
            "extension": "zip",
            "file_key": "synthetic/masking.zip",
            "title": "Original archive",
        }
    )
    brd_result["artifacts"] = deepcopy(brd_result["outputs"])
    before = deepcopy(brd_result)
    result = await agent_module.orchestrator.fn({"start_workflow": True, "output_format": "Word"})
    assert result["artifacts"][1:] == before["artifacts"]
    assert result["outputs"] == before["outputs"]
    assert brd_result == before


class _Answer:
    """Minimal stand-in for HumanResponse."""

    def __init__(self, answer):
        self._answer = answer

    def value(self, name, default=None):
        assert name == "continue_to_fitmap"
        return self._answer


@pytest.fixture(autouse=True)
def ask(monkeypatch):
    """Consent is stubbed everywhere; No by default, so these tests stay at the BRD stage."""
    call = AsyncMock(return_value=_Answer("No"))
    monkeypatch.setattr(agent_module.humanInput, "request", call)
    return call


async def test_consent_card_is_asked_once_with_the_document(execute, ask):
    """The card's shape; the Yes path is covered in test_fitmap_handoff.py."""
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    ask.assert_awaited_once()
    prompt = ask.await_args.args[0]
    assert "BRD" in prompt
    assert ask.await_args.kwargs["timeout"].total_seconds() == 24 * 3600
    assert ask.await_args.kwargs["on_timeout"] == "return_none"
    field = ask.await_args.kwargs["fields"][0]
    assert field.name == "continue_to_fitmap"
    assert field.options == ("Yes", "No")
    assert field.required is True
    assert result["continue_decision"] == "No"
    assert result["outputs"] == execute.return_value["outputs"]


@pytest.mark.parametrize(
    ("answer", "decision", "phrase"),
    [("No", "No", "Stopping with the BRD"), ("no", "No", "Stopping with the BRD")],
)
async def test_declining_keeps_the_brd(execute, monkeypatch, answer, decision, phrase):
    monkeypatch.setattr(agent_module.humanInput, "request", AsyncMock(return_value=_Answer(answer)))
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    assert result["continue_decision"] == decision
    assert phrase in result["message"]
    assert result["status"] == "success"
    assert result["outputs"] == execute.return_value["outputs"]


async def test_timeout_is_not_consent(execute, monkeypatch):
    monkeypatch.setattr(agent_module.humanInput, "request", AsyncMock(return_value=None))
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    assert result["continue_decision"] == "timeout"
    assert "No answer within 24 hours" in result["message"]
    assert result["outputs"] == execute.return_value["outputs"]


async def test_unrecognised_answer_is_not_consent(execute, monkeypatch):
    monkeypatch.setattr(
        agent_module.humanInput, "request", AsyncMock(return_value=_Answer("maybe later"))
    )
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    assert result["continue_decision"] == "No"


async def test_failed_brd_is_never_offered_a_decision(monkeypatch, ask):
    monkeypatch.setattr(
        agent_module.agentExecutor,
        "execute",
        AsyncMock(return_value={"status": "cancelled", "outputs": [], "artifacts": []}),
    )
    monkeypatch.setattr(
        agent_module.workflow, "info", lambda: SimpleNamespace(workflow_id="root-test")
    )
    monkeypatch.setattr(agent_module.workflow, "uuid4", lambda: CHILD_UUID)
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    ask.assert_not_awaited()
    assert "continue_decision" not in result
    assert result["status"] == "cancelled"


async def test_partial_warnings_are_shown_before_consent(monkeypatch, ask, brd_result):
    partial = {**brd_result, "status": "partial", "warning": "Two chunks were skipped."}
    monkeypatch.setattr(agent_module.agentExecutor, "execute", AsyncMock(return_value=partial))
    monkeypatch.setattr(
        agent_module.workflow, "info", lambda: SimpleNamespace(workflow_id="root-test")
    )
    monkeypatch.setattr(agent_module.workflow, "uuid4", lambda: CHILD_UUID)
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    assert "Two chunks were skipped." in ask.await_args.args[0]
    assert "Two chunks were skipped." in result["message"]


@pytest.mark.parametrize(
    "outputs",
    [
        [],
        [{"type": "s3_download_link", "extension": "zip", "file_key": "out/masking.zip"}],
        [{"type": "inline", "extension": "xlsx", "file_key": "out/requirements.xlsx"}],
    ],
)
def test_no_usable_requirements_document_is_refused(outputs):
    """validate_brd_result normally catches this first; the guard must still hold."""
    with pytest.raises(ValueError):
        select_brd_document({"status": "success", "outputs": outputs})
