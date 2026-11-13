"""FitMap handoff tests; no platform calls are made."""

import uuid
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from temporalio.exceptions import CancelledError, ChildWorkflowError

from src.agent import schemas
from src.agent.fitmap import (
    build_fitmap_payload,
    fitmap_artifacts,
    validate_fitmap_result,
)

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
        {
            "start_workflow": True,
            "start_from": "BRDGen",
            "task_metadata": {"conversation_id": "synthetic-chat"},
        }
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
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "BRDGen"})
    assert brd_result["outputs"][0] in result["artifacts"]
    assert fitmap_result["artifacts"][0] in result["artifacts"]
    assert result["outputs"] == brd_result["outputs"]


async def test_declining_never_starts_fitmap(children, monkeypatch):
    monkeypatch.setattr(
        agent_module.humanInput,
        "request",
        AsyncMock(return_value=SimpleNamespace(value=lambda name, default=None: "No")),
    )
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "BRDGen"})
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
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "BRDGen"})
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
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "BRDGen"})
    assert result["status"] == "cancelled"
    assert result["brd_status"] == "success"
    assert result["outputs"] == brd_result["outputs"]


async def test_starting_at_fitmap_skips_generation_and_the_consent_card(monkeypatch, fitmap_result):
    """Choosing FitMap is itself the request to analyse, so there is nothing to consent
    to afterwards: the only question left is FitMap's own TestCraft offer, which is
    FitMap's to ask."""
    call = AsyncMock(return_value=fitmap_result)
    monkeypatch.setattr(agent_module.agentExecutor, "execute", call)
    monkeypatch.setattr(agent_module.workflow, "uuid4", lambda: FITMAP_UUID)
    ask = AsyncMock()
    monkeypatch.setattr(agent_module.humanInput, "request", ask)
    result = await agent_module.orchestrator.fn(
        {"start_workflow": True, "start_from": "FitMap", "brd_file": BRD_KEY}
    )
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
    result = await agent_module.orchestrator.fn(
        {"start_workflow": True, "start_from": "FitMap", "brd_file": bad}
    )
    assert result["status"] == "invalid_input"
    # No BRD was generated here, so the stage must not claim one.
    assert result["stage"] == "fitgap"
    fitmap_only.assert_not_awaited()


@pytest.mark.parametrize("bad", ["../brd.xlsx", "https://example.com/brd.xlsx", "..\\brd.xlsx"])
async def test_recovery_refuses_an_unsafe_brd_reference(fitmap_only, bad):
    """A malformed or unsafe reference is a caller's mistake, not a user's choice, so
    it stops the run rather than quietly becoming "no document"."""
    result = await agent_module.orchestrator.fn(
        {"start_workflow": True, "start_from": "FitMap", "brd_file": bad}
    )
    assert result["status"] == "invalid_input"
    assert result["stage"] == "fitgap"
    fitmap_only.assert_not_awaited()


@pytest.mark.parametrize("ignored", ["", "   ", None])
async def test_an_empty_brd_field_is_not_an_attachment(fitmap_only, ignored, fitmap_result):
    """The platform sends a blank for a file field left empty. Treating it as a
    document makes FitMap fail instead of opening its own upload card."""
    fitmap_only.return_value = fitmap_result
    await agent_module.orchestrator.fn(
        {"start_workflow": True, "start_from": "FitMap", "brd_file": ignored}
    )
    child_payload = fitmap_only.await_args.args[1]
    assert "brd_file" not in child_payload


@pytest.mark.parametrize("wrong_type", ["notes/fitgap.md", "notes/transcript.txt"])
async def test_a_type_fitmap_cannot_read_is_explained_not_fatal(
    fitmap_only, wrong_type, fitmap_result
):
    """The file field accepts TestCraft's types too, so a .md can reach a FitMap start.
    FitMap cannot read one: it must ask for a document it can, and say why."""
    fitmap_only.return_value = fitmap_result
    result = await agent_module.orchestrator.fn(
        {"start_workflow": True, "start_from": "FitMap", "brd_file": wrong_type}
    )
    fitmap_only.assert_awaited_once()
    child_payload = fitmap_only.await_args.args[1]
    # Never handed a file it cannot open.
    assert "brd_file" not in child_payload
    assert "was not used" in result["message"]
    assert "FitMap does not read that file type" in result["message"]
    assert result["artifacts"][0]["text"] == result["message"]


async def test_recovery_reports_a_failed_fitmap_run_by_id(fitmap_only):
    fitmap_only.side_effect = _child_failure()
    result = await agent_module.orchestrator.fn(
        {"start_workflow": True, "start_from": "FitMap", "brd_file": BRD_KEY}
    )
    assert result["status"] == "error"
    assert result["stage"] == "fitgap"
    # The run id is what makes the failure traceable.
    assert result["fitmap_workflow_id"] == str(FITMAP_UUID)
    assert "sensitive internal error" not in result["message"]


async def test_recovery_refuses_an_unrecognised_fitmap_result(fitmap_only):
    fitmap_only.return_value = {"status": "finished"}
    result = await agent_module.orchestrator.fn(
        {"start_workflow": True, "start_from": "FitMap", "brd_file": BRD_KEY}
    )
    assert result["status"] == "error"
    assert result["stage"] == "fitgap"
    assert result["fitmap_workflow_id"] == str(FITMAP_UUID)


async def test_recovery_cancellation_is_not_converted_to_a_generic_failure(fitmap_only):
    cancelled = _child_failure("cancelled")
    cancelled.__cause__ = CancelledError("cancelled")
    fitmap_only.side_effect = cancelled
    with pytest.raises(ChildWorkflowError):
        await agent_module.orchestrator.fn(
            {"start_workflow": True, "start_from": "FitMap", "brd_file": BRD_KEY}
        )


async def test_consent_path_names_the_failed_fitmap_run(children):
    children.side_effect = [children.side_effect.__next__(), _child_failure()]
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "BRDGen"})
    assert result["stage"] == "brd"
    assert result["continue_decision"] == "Yes"
    assert result["fitmap_workflow_id"] == str(FITMAP_UUID)
    assert result["outputs"][0]["file_key"] == BRD_KEY


async def test_consent_path_keeps_the_brd_when_fitmap_returns_nonsense(children):
    children.side_effect = [children.side_effect.__next__(), {"status": "finished"}]
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "BRDGen"})
    assert result["stage"] == "brd"
    assert result["fitmap_workflow_id"] == str(FITMAP_UUID)
    assert result["outputs"][0]["file_key"] == BRD_KEY


async def test_consent_path_cancellation_propagates(children):
    cancelled = _child_failure("cancelled")
    cancelled.__cause__ = CancelledError("cancelled")
    children.side_effect = [children.side_effect.__next__(), cancelled]
    with pytest.raises(ChildWorkflowError):
        await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "BRDGen"})


def test_carried_fields_stay_in_step_with_the_schema():
    """BRD_RESULT_FIELDS promises these are declared; drift would silently drop them."""
    declared = {field["name"] for field in schemas.OUTPUT_SCHEMA}
    assert set(schemas.BRD_RESULT_FIELDS) <= declared


async def test_every_brd_owned_field_survives_fitmap(children, brd_result):
    """Spreading FitMap's result must not erase anything BRDGen declared."""
    supplied = {
        "warning": "Extraction failed for 2 of 9 transcript chunk(s).",
        "consolidation_warning": "Requirements were not consolidated.",
        "skipped_files": [{"file": "notes.txt", "issue": "unreadable"}],
        "used_despite_issues": [{"file": "calls.txt", "issue": "no match"}],
    }
    # Every declared field is exercised, so adding one without carrying it fails here.
    assert set(supplied) == set(schemas.BRD_RESULT_FIELDS)
    brd_result.update(supplied)
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "BRDGen"})
    assert result["status"] == "success"
    assert result["stage"] == "fitgap"
    for field, value in supplied.items():
        assert result[field] == value
    # The warnings stay readable by a human too, not only by a schema consumer.
    assert "Extraction failed for 2 of 9 transcript chunk(s)." in result["message"]


async def test_undeclared_brd_counts_are_not_carried(children, brd_result):
    """BRDGen's counts use a numeric type no agent here declares, so they stay out of
    the registered contract rather than being smuggled through."""
    brd_result["process_row_count"] = 40
    brd_result["masked_entity_count"] = 17
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "BRDGen"})
    assert "process_row_count" not in result
    assert "masked_entity_count" not in result


async def test_fields_brdgen_did_not_set_are_not_invented(children, brd_result):
    """A run with nothing to report must not gain empty fields."""
    brd_result["warning"] = "Extraction failed for 2 of 9 transcript chunk(s)."
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "BRDGen"})
    assert result["warning"] == brd_result["warning"]
    for field in schemas.BRD_RESULT_FIELDS:
        if field != "warning":
            assert field not in result


async def test_a_fitmap_field_is_not_blanked_by_an_absent_brd_one(children, fitmap_result):
    """FitMap returns no warning today; if it ever does, an empty BRD must not win."""
    fitmap_result["warning"] = "FitMap's own warning."
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "BRDGen"})
    assert result["warning"] == "FitMap's own warning."


async def test_a_supplied_brd_is_never_dropped_without_the_start_flag(monkeypatch):
    """A file can arrive on a turn the platform did not mark as a start."""
    execute = AsyncMock()
    monkeypatch.setattr(agent_module.agentExecutor, "execute", execute)
    result = await agent_module.orchestrator.fn({"brd_file": BRD_KEY})
    # Named, not started: nothing runs without an explicit request.
    execute.assert_not_awaited()
    assert result["status"] == "ready"
    assert result["stage"] == "start"
    # The file is acknowledged, but which agent gets it is still the user's to say.
    assert "document you attached" in result["message"]


async def test_the_plain_ready_reply_names_all_three_agents(monkeypatch):
    execute = AsyncMock()
    monkeypatch.setattr(agent_module.agentExecutor, "execute", execute)
    result = await agent_module.orchestrator.fn({})
    execute.assert_not_awaited()
    assert result["status"] == "ready"
    assert result["stage"] == "start"
    for name in ("BRDGen", "FitMap", "TestCraft"):
        assert name in result["message"]


async def test_a_brd_error_string_is_never_carried_onto_a_successful_analysis(children, brd_result):
    """Same rule as brd_notices: `error` is BRDGen's failure text, so a result whose
    status is FitMap's success must not carry one. It is deliberately absent from
    BRD_RESULT_FIELDS."""
    brd_result["error"] = "stale note from BRDGen"
    assert "error" not in schemas.BRD_RESULT_FIELDS
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "BRDGen"})
    assert result["status"] == "success"
    assert "error" not in result
