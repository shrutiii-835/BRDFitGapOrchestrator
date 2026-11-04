"""FitMap handoff tests; no platform calls are made."""

import uuid
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from temporalio.exceptions import CancelledError, ChildWorkflowError

from src.agent.fitmap import build_fitmap_payload, fitmap_artifacts, validate_fitmap_result

agent_module = import_module("src.agent.agent")

BRD_UUID = uuid.UUID("00000000-0000-4000-8000-00000000b2d0")
FITMAP_UUID = uuid.UUID("00000000-0000-4000-8000-00000000f17a")
BRD_KEY = "synthetic-output/requirements.xlsx"


@pytest.fixture
def brd_result():
    return {
        "status": "success",
        "outputs": [
            {
                "type": "s3_download_link",
                "extension": "xlsx",
                "file_key": BRD_KEY,
                "title": "BRD",
            }
        ],
    }


@pytest.fixture
def fitmap_result():
    return {
        "status": "success",
        "message": "Analysis complete: 12 fits, 3 gaps.",
        "summary": "12 fits, 3 gaps.",
        "analysis_report": {
            "type": "s3_download_link",
            "file_key": "synthetic-output/fitgap.xlsx",
        },
        "client_report": {"type": "s3_download_link", "file_key": "synthetic-output/report.pdf"},
        "artifacts": [{"title": "Fit-Gap", "text": "12 fits, 3 gaps."}],
        "testcraft": {"status": "declined"},
    }


@pytest.fixture
def children(monkeypatch, brd_result, fitmap_result):
    """BRDGen then FitMap, in the order the workflow calls them."""
    call = AsyncMock(side_effect=[brd_result, fitmap_result])
    monkeypatch.setattr(agent_module.agentExecutor, "execute", call)
    monkeypatch.setattr(
        agent_module.workflow, "info", lambda: SimpleNamespace(workflow_id="root-test")
    )
    ids = iter([BRD_UUID, FITMAP_UUID])
    monkeypatch.setattr(agent_module.workflow, "uuid4", lambda: next(ids))
    monkeypatch.setattr(
        agent_module.humanInput,
        "request",
        AsyncMock(return_value=SimpleNamespace(value=lambda name, default=None: "Yes")),
    )
    return call


async def test_fitmap_receives_the_brd_and_owns_its_own_choices(children, fitmap_result):
    result = await agent_module.orchestrator.fn(
        {"start_workflow": True, "task_metadata": {"conversation_id": "synthetic-chat"}}
    )
    assert children.await_count == 2
    name, child_payload = children.await_args_list[1].args
    assert name == "FitMap"
    assert child_payload["brd_file"] == BRD_KEY
    assert child_payload["conversation_mode"] is True
    assert child_payload["start_analysis"] is True
    # FitMap and the user own these; the orchestrator must never supply them.
    for owned in ("oracle_product", "oracle_application", "offer_testcraft"):
        assert owned not in child_payload
    assert children.await_args_list[1].kwargs["workflow_id"] == str(FITMAP_UUID)
    assert children.await_args_list[1].kwargs["execution_timeout"].days == 2
    assert result["stage"] == "fitgap"
    assert result["status"] == "success"
    assert result["summary"] == fitmap_result["summary"]
    assert result["testcraft"] == {"status": "declined"}
    assert result["fitmap_workflow_id"] == str(FITMAP_UUID)
    assert result["brd_workflow_id"] == str(BRD_UUID)


async def test_both_agents_artifacts_are_returned(children, brd_result, fitmap_result):
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    assert brd_result["outputs"][0] in result["artifacts"]
    assert fitmap_result["artifacts"][0] in result["artifacts"]
    assert result["outputs"] == brd_result["outputs"]


async def test_declining_never_starts_fitmap(children, monkeypatch):
    monkeypatch.setattr(
        agent_module.humanInput,
        "request",
        AsyncMock(return_value=SimpleNamespace(value=lambda name, default=None: "No")),
    )
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    assert children.await_count == 1
    assert children.await_args_list[0].args[0] == "BRDGen"
    assert result["continue_decision"] == "No"
    assert result["stage"] == "brd"


async def test_failed_fitmap_keeps_the_brd(monkeypatch, brd_result):
    call = AsyncMock(
        side_effect=[
            brd_result,
            ChildWorkflowError(
                "sensitive internal error",
                namespace="synthetic",
                workflow_id="child",
                run_id="run",
                workflow_type="FitMap",
                initiated_event_id=1,
                started_event_id=2,
                retry_state=None,
            ),
        ]
    )
    monkeypatch.setattr(agent_module.agentExecutor, "execute", call)
    monkeypatch.setattr(
        agent_module.workflow, "info", lambda: SimpleNamespace(workflow_id="root-test")
    )
    ids = iter([BRD_UUID, FITMAP_UUID])
    monkeypatch.setattr(agent_module.workflow, "uuid4", lambda: next(ids))
    monkeypatch.setattr(
        agent_module.humanInput,
        "request",
        AsyncMock(return_value=SimpleNamespace(value=lambda name, default=None: "Yes")),
    )
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    assert result["status"] == "success"
    assert result["stage"] == "brd"
    assert result["outputs"] == brd_result["outputs"]
    assert "FitMap could not complete" in result["message"]
    assert "BRD is below" in result["message"]


async def test_unsuccessful_fitmap_status_is_not_dressed_up(monkeypatch, brd_result):
    refused = {"status": "cancelled", "message": "Cancelled at the Oracle product card."}
    call = AsyncMock(side_effect=[brd_result, refused])
    monkeypatch.setattr(agent_module.agentExecutor, "execute", call)
    monkeypatch.setattr(
        agent_module.workflow, "info", lambda: SimpleNamespace(workflow_id="root-test")
    )
    ids = iter([BRD_UUID, FITMAP_UUID])
    monkeypatch.setattr(agent_module.workflow, "uuid4", lambda: next(ids))
    monkeypatch.setattr(
        agent_module.humanInput,
        "request",
        AsyncMock(return_value=SimpleNamespace(value=lambda name, default=None: "Yes")),
    )
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    assert result["status"] == "cancelled"
    assert result["brd_status"] == "success"
    assert result["outputs"] == brd_result["outputs"]


async def test_existing_brd_skips_generation_and_the_question(monkeypatch, fitmap_result):
    call = AsyncMock(return_value=fitmap_result)
    monkeypatch.setattr(agent_module.agentExecutor, "execute", call)
    monkeypatch.setattr(agent_module.workflow, "uuid4", lambda: FITMAP_UUID)
    ask = AsyncMock()
    monkeypatch.setattr(agent_module.humanInput, "request", ask)
    result = await agent_module.orchestrator.fn({"start_workflow": True, "brd_file": BRD_KEY})
    call.assert_awaited_once()
    assert call.await_args.args[0] == "FitMap"
    ask.assert_not_awaited()
    assert result["stage"] == "fitgap"
    assert result["status"] == "success"


@pytest.mark.parametrize(
    "bad",
    ["", "https://example.com/brd.xlsx", "/tmp/brd.xlsx", "../brd.xlsx", "brd.txt", "brd"],
)
def test_unusable_brd_references_are_refused(bad):
    with pytest.raises(ValueError):
        build_fitmap_payload(bad, {})


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "done",
        {"status": "finished"},
        {"status": "success", "artifacts": "none"},
        {"status": "success", "analysis_report": {"file_key": "/tmp/x.xlsx"}},
        {"status": "success", "client_report": {"file_key": ""}},
    ],
)
def test_unrecognised_fitmap_results_are_refused(bad):
    with pytest.raises(ValueError):
        validate_fitmap_result(bad)


def test_documents_are_used_when_no_artifacts_are_returned():
    result = {
        "status": "success",
        "analysis_report": {"type": "s3_download_link", "file_key": "out/fitgap.xlsx"},
        "client_report": {"type": "s3_download_link", "file_key": "out/report.pdf"},
    }
    assert fitmap_artifacts(validate_fitmap_result(result)) == [
        result["analysis_report"],
        result["client_report"],
    ]


def test_task_metadata_is_copied_not_shared():
    payload = {"task_metadata": {"conversation_id": "synthetic"}}
    child = build_fitmap_payload(BRD_KEY, payload)
    assert child["task_metadata"] == payload["task_metadata"]
    assert child["task_metadata"] is not payload["task_metadata"]


def _child_failure(message: str = "sensitive internal error") -> ChildWorkflowError:
    return ChildWorkflowError(
        message,
        namespace="synthetic",
        workflow_id="child",
        run_id="run",
        workflow_type="FitMap",
        initiated_event_id=1,
        started_event_id=2,
        retry_state=None,
    )


@pytest.fixture
def fitmap_only(monkeypatch):
    """The recovery path: a supplied BRD, so FitMap is the only child."""
    call = AsyncMock()
    monkeypatch.setattr(agent_module.agentExecutor, "execute", call)
    monkeypatch.setattr(agent_module.workflow, "uuid4", lambda: FITMAP_UUID)
    monkeypatch.setattr(agent_module.humanInput, "request", AsyncMock())
    return call


@pytest.mark.parametrize("bad", [17, True, ["key"], {"file_key": BRD_KEY}])
async def test_recovery_refuses_a_brd_file_that_is_not_a_key(fitmap_only, bad):
    result = await agent_module.orchestrator.fn({"start_workflow": True, "brd_file": bad})
    assert result["status"] == "invalid_input"
    # No BRD was generated here, so the stage must not claim one.
    assert result["stage"] == "fitgap"
    fitmap_only.assert_not_awaited()


@pytest.mark.parametrize("bad", ["", "../brd.xlsx", "https://example.com/brd.xlsx", "brd.txt"])
async def test_recovery_refuses_an_unusable_brd_reference(fitmap_only, bad):
    result = await agent_module.orchestrator.fn({"start_workflow": True, "brd_file": bad})
    assert result["status"] == "invalid_input"
    assert result["stage"] == "fitgap"
    fitmap_only.assert_not_awaited()


async def test_recovery_reports_a_failed_fitmap_run_by_id(fitmap_only):
    fitmap_only.side_effect = _child_failure()
    result = await agent_module.orchestrator.fn({"start_workflow": True, "brd_file": BRD_KEY})
    assert result["status"] == "error"
    assert result["stage"] == "fitgap"
    # The run id is what makes the failure traceable.
    assert result["fitmap_workflow_id"] == str(FITMAP_UUID)
    assert "sensitive internal error" not in result["message"]


async def test_recovery_refuses_an_unrecognised_fitmap_result(fitmap_only):
    fitmap_only.return_value = {"status": "finished"}
    result = await agent_module.orchestrator.fn({"start_workflow": True, "brd_file": BRD_KEY})
    assert result["status"] == "error"
    assert result["stage"] == "fitgap"
    assert result["fitmap_workflow_id"] == str(FITMAP_UUID)


async def test_recovery_cancellation_is_not_converted_to_a_generic_failure(fitmap_only):
    cancelled = _child_failure("cancelled")
    cancelled.__cause__ = CancelledError("cancelled")
    fitmap_only.side_effect = cancelled
    with pytest.raises(ChildWorkflowError):
        await agent_module.orchestrator.fn({"start_workflow": True, "brd_file": BRD_KEY})


async def test_consent_path_names_the_failed_fitmap_run(children):
    children.side_effect = [children.side_effect.__next__(), _child_failure()]
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    assert result["stage"] == "brd"
    assert result["continue_decision"] == "Yes"
    assert result["fitmap_workflow_id"] == str(FITMAP_UUID)
    assert result["outputs"][0]["file_key"] == BRD_KEY


async def test_consent_path_keeps_the_brd_when_fitmap_returns_nonsense(children):
    children.side_effect = [children.side_effect.__next__(), {"status": "finished"}]
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    assert result["stage"] == "brd"
    assert result["fitmap_workflow_id"] == str(FITMAP_UUID)
    assert result["outputs"][0]["file_key"] == BRD_KEY


async def test_consent_path_cancellation_propagates(children):
    cancelled = _child_failure("cancelled")
    cancelled.__cause__ = CancelledError("cancelled")
    children.side_effect = [children.side_effect.__next__(), cancelled]
    with pytest.raises(ChildWorkflowError):
        await agent_module.orchestrator.fn({"start_workflow": True})
