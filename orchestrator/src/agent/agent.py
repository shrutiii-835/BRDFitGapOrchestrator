"""BRDGen, an explicit continuation decision, then FitMap; neither child is modified."""

from __future__ import annotations

from datetime import timedelta
from importlib import resources
from typing import Any

from aetherion_sdk import Field, agent, agentExecutor, humanInput, register
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ChildWorkflowError, is_cancelled_exception

from src.agent.brd import (
    brd_notices,
    build_brd_payload,
    select_brd_document,
    validate_brd_result,
)
from src.agent.fitmap import build_fitmap_payload, fitmap_artifacts, validate_fitmap_result
from src.agent.schemas import AGENT_NAME, BRD_RESULT_FIELDS, INPUT_SCHEMA, OUTPUT_SCHEMA

_DESCRIPTION = (
    resources.files("src.agent.prompts").joinpath("conversation.md").read_text(encoding="utf-8")
)


_CONTINUE_TIMEOUT = timedelta(hours=24)
# Covers FitMap's own Oracle selection cards and the TestCraft offer it may make.
_FITMAP_TIMEOUT = timedelta(days=2)


async def _ask_continue(document: dict[str, Any], notices: list[str]) -> str:
    """Ask once, explicitly. Silence is never consent: a timeout stops with the BRD."""
    prompt = (
        f"Your BRD is ready: {document.get('title') or document['file_key']}.\n\n"
        "Do you want to continue to the Oracle fit-gap analysis?"
    )
    if notices:
        prompt += "\n\nBRDGen reported:\n" + "\n".join(notices)
    response = await humanInput.request(
        prompt,
        request_type="input",
        fields=[
            Field(
                name="continue_to_fitmap",
                type="choice",
                friendly_name="Continue to fit-gap analysis",
                options=("Yes", "No"),
                required=True,
            )
        ],
        metadata={"title": "Continue to fit-gap analysis?"},
        step_id="fitmap_consent",
        timeout=_CONTINUE_TIMEOUT,
        on_timeout="return_none",
    )
    if response is None:
        return "timeout"
    answer = response.value("continue_to_fitmap")
    return "Yes" if isinstance(answer, str) and answer.strip().lower() == "yes" else "No"


async def _run_fitmap(child_id: str, child_payload: dict[str, Any]) -> dict[str, Any]:
    """Start FitMap under an id the caller owns, so a failure can still name the run."""
    child_result = await agentExecutor.execute(
        "FitMap",
        child_payload,
        workflow_id=child_id,
        execution_timeout=_FITMAP_TIMEOUT,
        retry_policy=RetryPolicy(maximum_attempts=1),
    )
    return validate_fitmap_result(child_result)


def _new_child_id() -> str:
    """A bare uuid for a child run. Do not make this readable.

    The platform creates a child agent run record only for a plain uuid, and the
    child's human-input cards need that record to attach to. This mirrors how FitMap
    starts its own interactive child: AetherionAgents/fit_gap_agent PR #22,
    `_run_testcraft` - "A bare uuid: supernova gives only those a child agent_run,
    which HITL cards need."

    Confirmed the hard way here too. Version 0.0.2 used a derived id (`<parent>-brd`);
    BRDGen started, its register_human_input_request activity failed three times, and
    its upload card never reached the user, so the run hung with nothing on screen. A
    bare uuid in 0.0.3 fixed it - run f764134c-c6d7-4d4a-95e2-78c3cf306aa2 shows all
    three of BRDGen's cards arriving against child
    61f57005-c84a-41d3-918e-cafbf2579843.

    workflow.uuid4 rather than uuid.uuid4: Temporal replays this function, and a
    non-deterministic id would produce a different child on replay.
    """
    return str(workflow.uuid4())


async def _run_fitmap_only(brd_file_key: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Analyse a BRD the user already has, without regenerating it."""
    if not isinstance(brd_file_key, str):
        return _response(
            "invalid_input",
            "brd_file must be the storage key of an existing BRD document.",
            stage="fitgap",
        )
    try:
        child_payload = build_fitmap_payload(brd_file_key, payload)
    except ValueError as exc:
        return _response("invalid_input", str(exc), stage="fitgap")

    fitmap_id = _new_child_id()
    workflow.logger.info("Analysing a supplied BRD; FitMap run %s.", fitmap_id)
    try:
        analysis = await _run_fitmap(fitmap_id, child_payload)
    except ChildWorkflowError as exc:
        if is_cancelled_exception(exc):
            raise
        workflow.logger.warning("FitMap run %s did not complete.", fitmap_id)
        return _response(
            "error",
            "FitMap could not complete. Inspect its run before retrying.",
            stage="fitgap",
            fitmap_workflow_id=fitmap_id,
        )
    except ValueError as exc:
        workflow.logger.warning("FitMap run %s returned an unusable result.", fitmap_id)
        return _response("error", str(exc), stage="fitgap", fitmap_workflow_id=fitmap_id)
    workflow.logger.info("FitMap run %s finished with status %s.", fitmap_id, analysis["status"])
    return {
        **analysis,
        "stage": "fitgap",
        "fitmap_workflow_id": fitmap_id,
        "message": analysis.get("message") or "FitMap finished; its results are below.",
        "artifacts": [
            {"title": "BRD-FitGap Orchestrator", "text": "Analysed the BRD you supplied."},
            *fitmap_artifacts(analysis),
        ],
    }


async def _continue_to_fitmap(
    result: dict[str, Any],
    child_id: str,
    document: dict[str, Any],
    notices: list[str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Run FitMap after consent; the BRD survives whatever FitMap does."""
    brd_artifacts = result.get("artifacts") or result.get("outputs") or []
    try:
        child_payload = build_fitmap_payload(document["file_key"], payload)
    except ValueError as exc:
        return _finish(result, child_id, _with_notices(str(exc), notices), decision="Yes")

    fitmap_id = _new_child_id()
    workflow.logger.info("Consent given; starting FitMap run %s.", fitmap_id)
    try:
        analysis = await _run_fitmap(fitmap_id, child_payload)
    except ChildWorkflowError as exc:
        if is_cancelled_exception(exc):
            raise
        workflow.logger.warning("FitMap run %s did not complete; returning the BRD.", fitmap_id)
        return _finish(
            result,
            child_id,
            _with_notices(
                "FitMap could not complete, so there is no fit-gap analysis. "
                "Your BRD is below and is unaffected.",
                notices,
            ),
            decision="Yes",
            fitmap_id=fitmap_id,
        )
    except ValueError as exc:
        workflow.logger.warning("FitMap run %s returned an unusable result.", fitmap_id)
        return _finish(
            result,
            child_id,
            _with_notices(str(exc), notices),
            decision="Yes",
            fitmap_id=fitmap_id,
        )

    workflow.logger.info("FitMap run %s finished with status %s.", fitmap_id, analysis["status"])

    message = analysis.get("message") or "FitMap finished; its results are below."
    if analysis["status"] != "success":
        message += " Your BRD is below and is unaffected."
    # FitMap's result is the base below, so BRDGen's own OUTPUT_SCHEMA fields have to be
    # put back or they survive only as message text and `result["warning"]` returns None.
    # Values BRDGen did not set are skipped, so a field FitMap did set is never blanked.
    carried = {
        field: result[field] for field in BRD_RESULT_FIELDS if _is_present(result.get(field))
    }
    return {
        **analysis,
        **carried,
        "status": analysis["status"],
        "stage": "fitgap",
        "brd_status": result["status"],
        "brd_workflow_id": child_id,
        "fitmap_workflow_id": fitmap_id,
        "continue_decision": "Yes",
        "outputs": result.get("outputs", []),
        "message": _with_notices(message, notices),
        "artifacts": [
            {"title": "BRD-FitGap Orchestrator", "text": _with_notices(message, notices)},
            *brd_artifacts,
            *fitmap_artifacts(analysis),
        ],
    }


def _is_present(value: Any) -> bool:
    """Carry a value BRDGen actually set; a blank string or absent field is not one."""
    if value is None:
        return False
    return bool(value.strip()) if isinstance(value, str) else True


def _with_notices(message: str, notices: list[str]) -> str:
    return message + "\n\n" + "\n".join(notices) if notices else message


def _finish(
    result: dict[str, Any],
    child_id: str,
    message: str,
    decision: str | None = None,
    fitmap_id: str | None = None,
) -> dict[str, Any]:
    """Return BRDGen's own result and artifacts, whatever the decision was."""
    artifacts = result.get("artifacts") or result.get("outputs") or []
    finished = {
        **result,
        "stage": "brd",
        "brd_workflow_id": child_id,
        "message": message,
        "artifacts": [{"title": "BRD-FitGap Orchestrator", "text": message}, *artifacts],
    }
    if decision:
        finished["continue_decision"] = decision
    if fitmap_id:
        finished["fitmap_workflow_id"] = fitmap_id
    return finished


def _response(
    status: str,
    message: str,
    stage: str = "brd",
    brd_workflow_id: str | None = None,
    fitmap_workflow_id: str | None = None,
) -> dict[str, Any]:
    """A result with no child artifacts to carry, naming whichever run it concerns."""
    result: dict[str, Any] = {
        "status": status,
        "stage": stage,
        "message": message,
        "artifacts": [{"title": "BRD-FitGap Orchestrator", "text": message}],
    }
    if brd_workflow_id:
        result["brd_workflow_id"] = brd_workflow_id
    if fitmap_workflow_id:
        result["fitmap_workflow_id"] = fitmap_workflow_id
    return result


@register(
    name=AGENT_NAME,
    description=_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    output_schema=OUTPUT_SCHEMA,
    type="agent",
    chat_enabled=True,
    hitl_enabled=True,
)
@agent(name=AGENT_NAME, run_timeout=timedelta(days=7))
async def orchestrator(payload: dict[str, Any]) -> dict[str, Any]:
    """Run BRDGen, ask whether to continue, and run FitMap only on an explicit Yes."""
    if not isinstance(payload, dict):
        return _response("invalid_input", "The workflow input must be an object.")
    start = payload.get("start_workflow", False)
    if not isinstance(start, bool):
        return _response("invalid_input", "start_workflow must be true or false.")
    output_format = payload.get("output_format")
    if output_format is not None and output_format not in ("Excel", "Word"):
        return _response("invalid_input", "Choose Excel or Word as the output format.")
    # Read before the ready branch below. A BRD can arrive on a turn the platform did
    # not mark as a start - "is this format right for a fit-gap?" is a question, not a
    # request - and checking the flag first would drop that file without saying so.
    existing_brd = payload.get("brd_file")
    if not start:
        if existing_brd is not None:
            # Named, not started: the rest of this agent asks before running FitMap,
            # and an attached file is not clearer consent than an answered question.
            return _response(
                "ready",
                "I have your BRD and have not started anything yet. Say so and I will "
                "send it straight to FitMap for the Oracle fit-gap analysis, skipping "
                "BRD generation.",
                stage="fitgap",
            )
        return _response(
            "ready",
            "I run BRDGen with its existing uploads and review, then ask whether to "
            "continue to the Oracle fit-gap analysis with FitMap.",
        )

    # Recovery: an existing BRD skips generation. Supplying one and asking to start is
    # itself the request for analysis, so it needs no separate continuation question.
    if existing_brd is not None:
        return await _run_fitmap_only(existing_brd, payload)

    try:
        child_payload = build_brd_payload(payload)
    except ValueError as exc:
        return _response("invalid_input", str(exc))

    child_id = _new_child_id()
    workflow.logger.info("Starting BRDGen run %s.", child_id)
    try:
        child_result = await agentExecutor.execute(
            "BRDGen",
            child_payload,
            workflow_id=child_id,
            execution_timeout=timedelta(days=3),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
    except ChildWorkflowError as exc:
        if is_cancelled_exception(exc):
            raise
        workflow.logger.warning("BRDGen run %s did not complete; FitMap not started.", child_id)
        return _response(
            "error",
            "BRDGen could not complete. Inspect its run before retrying. FitMap was not started.",
            brd_workflow_id=child_id,
        )
    try:
        result = validate_brd_result(child_result)
    except ValueError as exc:
        workflow.logger.warning("BRDGen run %s returned an unusable result.", child_id)
        return _response("error", str(exc), brd_workflow_id=child_id)

    workflow.logger.info("BRDGen run %s finished with status %s.", child_id, result["status"])

    notices = brd_notices(result)
    if result["status"] not in ("success", "partial"):
        message = "BRDGen stopped without a completed BRD. FitMap was not started."
        if notices:
            message += "\n\n" + "\n".join(notices)
        return _finish(result, child_id, message)

    try:
        document = select_brd_document(result)
    except ValueError as exc:
        return _response("error", str(exc), brd_workflow_id=child_id)

    decision = await _ask_continue(document, notices)
    workflow.logger.info("Continuation decision: %s.", decision)
    if decision != "Yes":
        message = (
            "Stopping with the BRD, as you asked. FitMap was not started."
            if decision == "No"
            else "No answer within 24 hours, so I stopped with the BRD. FitMap was not started."
        )
        if notices:
            message += "\n\n" + "\n".join(notices)
        return _finish(result, child_id, message, decision=decision)

    return await _continue_to_fitmap(result, child_id, document, notices, payload)
