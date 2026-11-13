"""A chosen starting agent, then forward one agent at a time; no child is modified."""

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
    is_storage_key,
    select_brd_document,
    validate_brd_result,
)
from src.agent.fitmap import (
    BRD_EXTENSIONS,
    build_fitmap_payload,
    fitmap_artifacts,
    validate_fitmap_result,
)
from src.agent.schemas import (
    AGENT_NAME,
    BRD_RESULT_FIELDS,
    INPUT_SCHEMA,
    OUTPUT_SCHEMA,
    START_POINTS,
)
from src.agent.testcraft import (
    TESTCRAFT_EXTENSIONS,
    build_testcraft_payload,
    testcraft_artifacts,
    validate_testcraft_result,
)

_DESCRIPTION = (
    resources.files("src.agent.prompts").joinpath("conversation.md").read_text(encoding="utf-8")
)


# Stage timeouts. Each one is caught below and ends the run with an explanation and
# whatever was already produced, so these are the limits a real run is meant to hit.
_START_TIMEOUT = timedelta(hours=24)
_BRD_TIMEOUT = timedelta(days=3)
_CONTINUE_TIMEOUT = timedelta(hours=24)
# Matches FitMap's own run_timeout (4 days, fit_gap_agent/src/agent/workflow.py).
# A healthy FitMap run can legitimately need most of that: three intake cards at up
# to 24h each, the analysis, a 24h TestCraft offer and a TestCraft child of up to a
# day. Anything shorter here would kill FitMap mid-intake or mid-TestCraft.
_FITMAP_TIMEOUT = timedelta(days=4)
# TestCraft runs its own upload box, file check and three review gates
# (AetherionAgents/explora_polaris, src/agent/agents.py, commit 9e0eea7), so it is
# given the same room as FitMap rather than the minutes its processing takes.
_TESTCRAFT_TIMEOUT = timedelta(days=2)

# The run cap is the hard kill switch. Temporal's run_timeout cannot be caught: it ends
# the workflow with no result and takes the running child with it. It is here to reap a
# wedged run and must never be what stops a healthy one, so it is added up from the
# waits above rather than picked. Add a stage and the cap grows by that stage's timeout,
# with nobody having to remember to widen it.
#
# Every run waits for the start question, so that one is always counted. After it comes
# one of two routes, never both, so the cap takes the longer rather than the sum:
#
#   BRDGen route:    1 (start) + 3 (BRDGen) + 1 (continue?) + 4 (FitMap) = 9 days
#   TestCraft route: 1 (start) + 2 (TestCraft)                           = 3 days
#
# _SLACK covers the gaps between stages - validating a result, raising a card, the calls
# themselves. Those are minutes, not days, and do not grow when a stage does.
#
# 9 + 1 slack = 10 days. It was 8 while FitMap was given only 2 days; raising FitMap to
# its own 4-day limit grew the cap by the same 2 days. That is the sum working, not a
# separate decision.
_SLACK = timedelta(days=1)
_BRD_CHAIN = _BRD_TIMEOUT + _CONTINUE_TIMEOUT + _FITMAP_TIMEOUT
_RUN_TIMEOUT = _START_TIMEOUT + max(_BRD_CHAIN, _TESTCRAFT_TIMEOUT) + _SLACK


# A card the user closed or rejected, as FitMap's intake treats it (workflow.py).
_CANCEL_ACTIONS = ("cancel", "reject")


class _ChoiceField(Field):
    """A choice field the chat renders as a numbered selection card.

    The SDK's default spec sends options as ``[{"value": ...}]``, which the chat
    does not draw as selectable options. FitMap's intake cards send them as a
    plain list of strings (fit_gap_agent/src/agent/workflow.py, ``_UIField``),
    and that is what renders the numbered radio list, so the same spec is used here.
    """

    def to_field_spec(self) -> dict[str, Any]:
        spec = super().to_field_spec()
        if self.type == "choice":
            spec["options"] = list(self.options or ())
        return spec


def _named_start_point(value: Any) -> str | None:
    """Match a supplied start_from to one of the three agents, or None if it is not one."""
    if not isinstance(value, str):
        return None
    wanted = value.strip().lower()
    return next((name for name in START_POINTS if name.lower() == wanted), None)


async def _ask_start_point() -> str:
    """Ask where to begin. No default: silence starts nothing, as everywhere else here.

    Returns the chosen agent, or why there is none: "timeout" when the card went
    unanswered, "cancelled" when the user closed or rejected it, "unclear" when the
    answer was not one of the three. None is a start point, but they are different
    things, and someone who answered should not be told they stayed silent. No word can
    collide with a real answer.
    """
    response = await humanInput.request(
        "I coordinate three agents. Which one do you want to start from?\n\n"
        "- **BRDGen** drafts a Business Requirements Document.\n"
        "- **FitMap** runs an Oracle fit-gap analysis on a BRD.\n"
        "- **TestCraft** generates test scenarios and scripts from a BRD or "
        "fit-gap document.\n\n"
        "Each later agent runs only if you agree.",
        request_type="input",
        fields=[
            _ChoiceField(
                name="start_from",
                type="choice",
                friendly_name="Start from",
                options=START_POINTS,
                required=True,
            )
        ],
        metadata={"title": "Where should this run start?", "step_label": "Choose agent"},
        step_id="start_point",
        timeout=_START_TIMEOUT,
        on_timeout="return_none",
    )
    if response is None:
        return "timeout"
    if response.action_type in _CANCEL_ACTIONS:
        return "cancelled"
    return _named_start_point(response.value("start_from")) or "unclear"


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
            _ChoiceField(
                name="continue_to_fitmap",
                type="choice",
                friendly_name="Continue to fit-gap analysis",
                options=("Yes", "No"),
                required=True,
            )
        ],
        metadata={"title": "Continue to fit-gap analysis?", "step_label": "BRD ready"},
        step_id="fitmap_consent",
        timeout=_CONTINUE_TIMEOUT,
        on_timeout="return_none",
    )
    if response is None:
        return "timeout"
    if response.action_type in _CANCEL_ACTIONS:
        return "cancelled"
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


async def _run_fitmap_only(
    brd_file_key: Any, payload: dict[str, Any], carried: list[str]
) -> dict[str, Any]:
    """Analyse a BRD, regenerating nothing.

    With no document at all FitMap opens its own upload card, the same way BRDGen and
    TestCraft collect their own inputs. Something supplied that is not a key is still
    refused here: that is a caller's mistake, not a user with nothing to attach.
    """
    # These two guards no longer fire: _run_from checks the reference for every agent
    # that receives one, before this is called. They stay as the boundary's own check,
    # so a future caller cannot reach FitMap with something unusable, and that is why
    # they are the uncovered lines in this module.
    if brd_file_key is not None and not isinstance(brd_file_key, str):
        return _response(
            "invalid_input",
            _with_notices("brd_file must be the storage key of an existing BRD document.", carried),
            stage="fitgap",
        )
    try:
        child_payload = build_fitmap_payload(brd_file_key, payload)
    except ValueError as exc:
        return _response("invalid_input", _with_notices(str(exc), carried), stage="fitgap")

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
            _with_notices("FitMap could not complete. Inspect its run before retrying.", carried),
            stage="fitgap",
            fitmap_workflow_id=fitmap_id,
        )
    except ValueError as exc:
        workflow.logger.warning("FitMap run %s returned an unusable result.", fitmap_id)
        return _response(
            "error", _with_notices(str(exc), carried), stage="fitgap", fitmap_workflow_id=fitmap_id
        )
    workflow.logger.info("FitMap run %s finished with status %s.", fitmap_id, analysis["status"])
    message = _with_notices(
        analysis.get("message") or "FitMap finished; its results are below.", carried
    )
    return {
        **analysis,
        "stage": "fitgap",
        "fitmap_workflow_id": fitmap_id,
        "message": message,
        "artifacts": [
            {"title": "BRD-FitGap Orchestrator", "text": message},
            *fitmap_artifacts(analysis),
        ],
    }


async def _run_testcraft_only(
    payload: dict[str, Any], document: Any, carried: list[str]
) -> dict[str, Any]:
    """Generate tests from a document the user already has, with no earlier stage.

    "TestCraft" is a literal at the call site, which is what lets the platform map the
    child's task queue. That is enough on its own: a live sbox/test run at 0.0.8 reached
    TestCraft by name and came back with its workbook, so the orchestrator needs none of
    the agents-table lookup FitMap does for the same child
    (AetherionAgents/fit_gap_agent, src/tools/agent_lookup.py), and takes on no database
    dependency for it.
    """
    child_payload = build_testcraft_payload(document)
    testcraft_id = _new_child_id()
    workflow.logger.info("Starting TestCraft run %s.", testcraft_id)
    try:
        child_result = await agentExecutor.execute(
            "TestCraft",
            child_payload,
            workflow_id=testcraft_id,
            execution_timeout=_TESTCRAFT_TIMEOUT,
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
    except ChildWorkflowError as exc:
        if is_cancelled_exception(exc):
            raise
        workflow.logger.warning("TestCraft run %s did not complete.", testcraft_id)
        return _response(
            "error",
            _with_notices(
                "TestCraft could not complete. Inspect its run before retrying.", carried
            ),
            stage="testcraft",
            testcraft_workflow_id=testcraft_id,
        )
    try:
        result = validate_testcraft_result(child_result)
    except ValueError as exc:
        workflow.logger.warning("TestCraft run %s returned an unusable result.", testcraft_id)
        return _response(
            "error",
            _with_notices(str(exc), carried),
            stage="testcraft",
            testcraft_workflow_id=testcraft_id,
        )

    workflow.logger.info(
        "TestCraft run %s finished with status %s.", testcraft_id, result["status"]
    )
    message = _with_notices(
        result.get("message") or result.get("reason") or "TestCraft finished.", carried
    )
    return {
        **result,
        "stage": "testcraft",
        "testcraft_workflow_id": testcraft_id,
        "message": message,
        "artifacts": [
            {"title": "BRD-FitGap Orchestrator", "text": message},
            *testcraft_artifacts(result),
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
    testcraft_workflow_id: str | None = None,
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
    if testcraft_workflow_id:
        result["testcraft_workflow_id"] = testcraft_workflow_id
    return result


def _attached(value: Any) -> bool:
    """A document the user actually attached.

    A blank string or an empty object is what the platform sends for a file field that
    was offered and left empty. Treating those as an attachment makes the agent claim
    to hold a file that does not exist.
    """
    if value is None:
        return False
    return bool(value.strip()) if isinstance(value, str) else bool(value)


def _unusable_notice(start_from: str, document: Any) -> str | None:
    """Why the attached document is not going to the chosen agent, or None if it is.

    This is about the file type only. A document the agent cannot read is never fatal
    and never forwarded: the agent opens its own upload card, and the user is told why
    rather than left wondering where their file went. A reference that is malformed or
    unsafe is a different thing - a caller's mistake, not a user's choice - and is
    refused by the caller of this function before it is reached.

    The accepted types are each child's own, read from its metadata and kept beside its
    payload builder, which re-checks them as the boundary guard.
    """
    if not _attached(document):
        return None
    if start_from == "BRDGen":
        # BRDGen writes a new BRD from transcripts and process listings. It has no
        # input for a finished document, so any file attached here goes unused.
        return (
            "The document you attached was not used. BRDGen writes a new BRD, so it has "
            "nowhere to put one. Start at FitMap to analyse it, or at TestCraft to "
            "generate tests from it."
        )
    accepted = BRD_EXTENSIONS if start_from == "FitMap" else TESTCRAFT_EXTENSIONS
    if not isinstance(document, str) or document.lower().endswith(accepted):
        return None
    return (
        f"The document you attached was not used: {start_from} does not read that file "
        f"type. It accepts {', '.join(accepted)}, and will ask you for one it can read."
    )


_RECEIVES_A_DOCUMENT = {"FitMap": "fitgap", "TestCraft": "testcraft"}


async def _run_from(start_from: str, payload: dict[str, Any], existing_brd: Any) -> dict[str, Any]:
    """Run the chosen agent. Each one offers the next itself; none is assumed."""
    # Checked once, here, for every agent the document can reach. A reference that is
    # malformed or unsafe is a caller's mistake and stops the run; doing this per agent
    # let one of them refuse it and the other drop it without a word.
    # BRDGen is exempt: it never receives the document, so its shape cannot matter.
    stage = _RECEIVES_A_DOCUMENT.get(start_from)
    if stage and _attached(existing_brd) and not is_storage_key(existing_brd):
        return _response(
            "invalid_input",
            "brd_file must be the storage key of an uploaded document.",
            stage=stage,
        )
    notice = _unusable_notice(start_from, existing_brd)
    carried = [notice] if notice else []
    # Withheld rather than forwarded, so no child is handed a file it cannot open.
    document = None if notice or not _attached(existing_brd) else existing_brd
    if start_from == "TestCraft":
        # No file is required: TestCraft opens its own upload box when it is handed
        # none, the same way BRDGen collects its own inputs.
        return await _run_testcraft_only(payload, document, carried)
    if start_from == "FitMap":
        # No document is required: FitMap asks for one itself when it is handed none.
        return await _run_fitmap_only(document, payload, carried)
    return await _run_brdgen(payload, carried)


async def _run_brdgen(payload: dict[str, Any], carried: list[str]) -> dict[str, Any]:
    """Generate the BRD, then ask whether to continue to FitMap.

    `carried` holds notices decided before BRDGen ran. They join BRDGen's own so a
    thing the orchestrator did not do is said once, in the same place as the rest.
    """
    try:
        child_payload = build_brd_payload(payload)
    except ValueError as exc:
        return _response("invalid_input", _with_notices(str(exc), carried))

    child_id = _new_child_id()
    workflow.logger.info("Starting BRDGen run %s.", child_id)
    try:
        child_result = await agentExecutor.execute(
            "BRDGen",
            child_payload,
            workflow_id=child_id,
            execution_timeout=_BRD_TIMEOUT,
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
    except ChildWorkflowError as exc:
        if is_cancelled_exception(exc):
            raise
        workflow.logger.warning("BRDGen run %s did not complete; FitMap not started.", child_id)
        return _response(
            "error",
            _with_notices(
                "BRDGen could not complete. Inspect its run before retrying. "
                "FitMap was not started.",
                carried,
            ),
            brd_workflow_id=child_id,
        )
    try:
        result = validate_brd_result(child_result)
    except ValueError as exc:
        workflow.logger.warning("BRDGen run %s returned an unusable result.", child_id)
        return _response("error", _with_notices(str(exc), carried), brd_workflow_id=child_id)

    workflow.logger.info("BRDGen run %s finished with status %s.", child_id, result["status"])

    # Kept apart on purpose. The consent card prints what BRDGen said under "BRDGen
    # reported:", so a notice this orchestrator wrote must not join that list - it
    # would put our words in the child's mouth. Both still reach the final message.
    reported = brd_notices(result)
    notices = carried + reported
    if result["status"] not in ("success", "partial"):
        message = "BRDGen stopped without a completed BRD. FitMap was not started."
        if notices:
            message += "\n\n" + "\n".join(notices)
        return _finish(result, child_id, message)

    try:
        document = select_brd_document(result)
    except ValueError as exc:
        return _response("error", _with_notices(str(exc), notices), brd_workflow_id=child_id)

    decision = await _ask_continue(document, reported)
    workflow.logger.info("Continuation decision: %s.", decision)
    if decision != "Yes":
        message = {
            "No": "Stopping with the BRD, as you asked. FitMap was not started.",
            "cancelled": "You closed the card, so I stopped with the BRD. FitMap was not started.",
        }.get(
            decision,
            "No answer within 24 hours, so I stopped with the BRD. FitMap was not started.",
        )
        if notices:
            message += "\n\n" + "\n".join(notices)
        return _finish(result, child_id, message, decision=decision)

    return await _continue_to_fitmap(result, child_id, document, notices, payload)


@register(
    name=AGENT_NAME,
    description=_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    output_schema=OUTPUT_SCHEMA,
    type="agent",
    chat_enabled=True,
    hitl_enabled=True,
)
@agent(name=AGENT_NAME, run_timeout=_RUN_TIMEOUT)
async def orchestrator(payload: dict[str, Any]) -> dict[str, Any]:
    """Ask where to start, run that agent, and let each one offer the next itself."""
    if not isinstance(payload, dict):
        return _response("invalid_input", "The workflow input must be an object.")
    start = payload.get("start_workflow", False)
    if not isinstance(start, bool):
        return _response("invalid_input", "start_workflow must be true or false.")
    output_format = payload.get("output_format")
    if output_format is not None and output_format not in ("Excel", "Word"):
        return _response("invalid_input", "Choose Excel or Word as the output format.")
    # `_attached`'s rule again: the platform sends a blank for a field that was offered
    # and left alone, and a blank is not a choice. Refusing one would stop the run
    # instead of showing the card that asks for the choice.
    requested = payload.get("start_from") or None
    if isinstance(requested, str) and not requested.strip():
        requested = None
    start_from = _named_start_point(requested)
    if requested is not None and start_from is None:
        return _response(
            "invalid_input",
            "Choose BRDGen, FitMap or TestCraft as the agent to start from.",
            stage="start",
        )
    # Read before the ready branch below. A document can arrive on a turn the platform
    # did not mark as a start - "is this format right for a fit-gap?" is a question, not
    # a request - and checking the flag first would drop that file without saying so.
    existing_brd = payload.get("brd_file")
    if not start:
        held = (
            " I have the document you attached; FitMap or TestCraft can use it."
            if _attached(existing_brd)
            else ""
        )
        return _response(
            "ready",
            "I can start at BRDGen, which generates a BRD, at FitMap, which analyses one "
            "against Oracle, or at TestCraft, which generates test scenarios and scripts. "
            "Ask me to start and I will check which one you want." + held,
            stage="start",
        )

    # Asked, never inferred. An attached document is not an answer: FitMap and TestCraft
    # both accept one, so the file says nothing about which the user wants.
    if start_from is None:
        answer = await _ask_start_point()
        if answer in ("timeout", "cancelled", "unclear"):
            workflow.logger.info("No start point chosen: %s.", answer)
            return _response(
                "cancelled",
                {
                    "timeout": "No answer within 24 hours, so nothing was started. Ask "
                    "me again when you know which agent you want to begin at.",
                    "cancelled": "You cancelled the start card, so nothing was started. "
                    "Ask me again whenever you want to begin.",
                }.get(
                    answer,
                    "That answer was not one of the three agents, so nothing was "
                    "started. Ask me again and choose BRDGen, FitMap or TestCraft.",
                ),
                stage="start",
            )
        start_from = answer

    workflow.logger.info("Starting the run at %s.", start_from)
    result = await _run_from(start_from, payload, existing_brd)
    result["start_from"] = start_from
    return result
