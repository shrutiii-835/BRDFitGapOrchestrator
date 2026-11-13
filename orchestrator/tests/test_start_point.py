"""The choice of starting agent; no platform calls are made."""

import uuid
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.agent.schemas import START_POINTS

agent_module = import_module("src.agent.agent")

CHILD_UUID = uuid.UUID("00000000-0000-4000-8000-00000000c0de")
BRD_KEY = "synthetic-output/requirements.xlsx"


class _Answer:
    """Minimal stand-in for HumanResponse."""

    def __init__(self, answer, expect="start_from", action_type="submit"):
        self._answer = answer
        self._expect = expect
        self.action_type = action_type

    def value(self, name, default=None):
        assert name == self._expect
        return self._answer


@pytest.fixture
def no_children(monkeypatch):
    """Nothing may be started while the start point is still unknown."""
    call = AsyncMock()
    monkeypatch.setattr(agent_module.agentExecutor, "execute", call)
    monkeypatch.setattr(agent_module.workflow, "uuid4", lambda: CHILD_UUID)
    monkeypatch.setattr(
        agent_module.workflow, "info", lambda: SimpleNamespace(workflow_id="root-test")
    )
    return call


@pytest.fixture
def ask(monkeypatch):
    call = AsyncMock(return_value=_Answer("TestCraft"))
    monkeypatch.setattr(agent_module.humanInput, "request", call)
    return call


async def test_the_card_offers_exactly_the_three_agents(no_children, ask, monkeypatch):
    monkeypatch.setattr(
        agent_module.agentExecutor,
        "execute",
        AsyncMock(
            return_value={
                "status": "success",
                "test_cases_document": {"file_key": "synthetic-output/tests.xlsx"},
            }
        ),
    )
    await agent_module.orchestrator.fn({"start_workflow": True})
    ask.assert_awaited_once()
    field = ask.await_args.kwargs["fields"][0]
    assert field.name == "start_from"
    assert field.options == START_POINTS == ("BRDGen", "FitMap", "TestCraft")
    assert field.required is True
    assert ask.await_args.kwargs["timeout"].total_seconds() == 24 * 3600
    assert ask.await_args.kwargs["on_timeout"] == "return_none"
    assert ask.await_args.kwargs["step_id"] == "start_point"


async def test_an_attached_document_does_not_answer_the_question(no_children, ask):
    """FitMap and TestCraft both accept one, so the file says nothing about which."""
    monkeypatch_answer = _Answer("FitMap")
    ask.return_value = monkeypatch_answer
    await agent_module.orchestrator.fn({"start_workflow": True, "brd_file": BRD_KEY})
    ask.assert_awaited_once()


@pytest.mark.parametrize("chosen", START_POINTS)
async def test_the_answer_decides_which_agent_runs(no_children, ask, chosen, monkeypatch):
    ask.return_value = _Answer(chosen)
    routed = AsyncMock(return_value={"status": "ready", "stage": "test", "message": "routed"})
    monkeypatch.setattr(agent_module, "_run_from", routed)
    result = await agent_module.orchestrator.fn({"start_workflow": True, "brd_file": BRD_KEY})
    assert routed.await_args.args[0] == chosen
    assert result["start_from"] == chosen


@pytest.mark.parametrize(
    ("supplied", "canonical"),
    [
        ("BRDGen", "BRDGen"),
        ("brdgen", "BRDGen"),
        ("  FitMap  ", "FitMap"),
        ("TESTCRAFT", "TestCraft"),
    ],
)
async def test_a_named_start_point_is_accepted_whatever_the_casing(
    no_children, supplied, canonical, monkeypatch
):
    ask = AsyncMock()
    monkeypatch.setattr(agent_module.humanInput, "request", ask)
    routed = AsyncMock(return_value={"status": "ready", "stage": "test", "message": "routed"})
    monkeypatch.setattr(agent_module, "_run_from", routed)
    result = await agent_module.orchestrator.fn(
        {"start_workflow": True, "start_from": supplied, "brd_file": BRD_KEY}
    )
    # Named, so there is nothing to ask.
    ask.assert_not_awaited()
    # Recorded under the one spelling the schema promises, not the user's.
    assert result["start_from"] == canonical
    assert routed.await_args.args[0] == canonical


@pytest.mark.parametrize("bad", ["Scout", "brd gen", 3, True, ["FitMap"]])
async def test_an_unrecognised_start_point_starts_nothing(no_children, bad, monkeypatch):
    ask = AsyncMock()
    monkeypatch.setattr(agent_module.humanInput, "request", ask)
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": bad})
    no_children.assert_not_awaited()
    ask.assert_not_awaited()
    assert result["status"] == "invalid_input"
    assert result["stage"] == "start"
    assert "BRDGen, FitMap or TestCraft" in result["message"]


async def test_silence_starts_nothing(no_children, monkeypatch):
    monkeypatch.setattr(agent_module.humanInput, "request", AsyncMock(return_value=None))
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    no_children.assert_not_awaited()
    assert result["status"] == "cancelled"
    assert result["stage"] == "start"
    assert "nothing was started" in result["message"]
    assert "start_from" not in result


async def test_an_unreadable_answer_starts_nothing(no_children, monkeypatch):
    """The same rule as the consent card: only a real choice counts as one."""
    monkeypatch.setattr(
        agent_module.humanInput, "request", AsyncMock(return_value=_Answer("whichever"))
    )
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    no_children.assert_not_awaited()
    assert result["status"] == "cancelled"
    assert result["stage"] == "start"


async def test_fitmap_without_a_document_collects_its_own(no_children, monkeypatch):
    """FitMap opens its own BRD upload card, so there is nothing to ask it for here."""
    monkeypatch.setattr(
        agent_module.humanInput, "request", AsyncMock(return_value=_Answer("FitMap"))
    )
    no_children.return_value = {"status": "success", "artifacts": []}
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    no_children.assert_awaited_once()
    name, child_payload = no_children.await_args.args
    assert name == "FitMap"
    assert child_payload == {"conversation_mode": True, "start_analysis": True}
    # No key invented to stand in for the one the user did not give.
    assert "brd_file" not in child_payload
    assert result["stage"] == "fitgap"
    assert result["start_from"] == "FitMap"


async def test_nothing_is_started_before_the_question_is_answered(no_children, monkeypatch):
    """The card must be raised before any child call, not after one."""
    order = []
    monkeypatch.setattr(
        agent_module.humanInput,
        "request",
        AsyncMock(side_effect=lambda *a, **k: order.append("ask") or _Answer("BRDGen")),
    )
    no_children.side_effect = lambda *a, **k: order.append("child") or {
        "status": "cancelled",
        "outputs": [],
        "artifacts": [],
    }
    await agent_module.orchestrator.fn({"start_workflow": True})
    assert order[0] == "ask"


@pytest.mark.parametrize("flag", ["yes", 1, None])
async def test_a_non_boolean_start_flag_is_still_refused(no_children, flag, monkeypatch):
    ask = AsyncMock()
    monkeypatch.setattr(agent_module.humanInput, "request", ask)
    result = await agent_module.orchestrator.fn({"start_workflow": flag, "start_from": "BRDGen"})
    ask.assert_not_awaited()
    no_children.assert_not_awaited()
    assert result["status"] == "invalid_input"


async def test_brdgen_never_drops_an_attached_document_without_saying_so(monkeypatch):
    """BRDGen has no input for a finished document, so the file goes unused. The one
    thing that must not happen is it disappearing silently."""
    monkeypatch.setattr(
        agent_module.agentExecutor,
        "execute",
        AsyncMock(return_value={"status": "cancelled", "outputs": [], "artifacts": []}),
    )
    monkeypatch.setattr(agent_module.workflow, "uuid4", lambda: CHILD_UUID)
    monkeypatch.setattr(
        agent_module.workflow, "info", lambda: SimpleNamespace(workflow_id="root-test")
    )
    monkeypatch.setattr(agent_module.humanInput, "request", AsyncMock())
    result = await agent_module.orchestrator.fn(
        {"start_workflow": True, "start_from": "BRDGen", "brd_file": BRD_KEY}
    )
    assert "was not used" in result["message"]
    assert "FitMap" in result["message"] and "TestCraft" in result["message"]


async def test_nothing_is_said_about_a_document_that_was_never_attached(monkeypatch):
    monkeypatch.setattr(
        agent_module.agentExecutor,
        "execute",
        AsyncMock(return_value={"status": "cancelled", "outputs": [], "artifacts": []}),
    )
    monkeypatch.setattr(agent_module.workflow, "uuid4", lambda: CHILD_UUID)
    monkeypatch.setattr(
        agent_module.workflow, "info", lambda: SimpleNamespace(workflow_id="root-test")
    )
    monkeypatch.setattr(agent_module.humanInput, "request", AsyncMock())
    result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": "BRDGen"})
    assert "was not used" not in result["message"]


async def test_an_unreadable_answer_is_not_reported_as_silence(no_children, monkeypatch):
    """Someone who answered must not be told they stayed silent: the two stop the run
    the same way but for different reasons, and the message has to say which."""
    monkeypatch.setattr(
        agent_module.humanInput, "request", AsyncMock(return_value=_Answer("whichever"))
    )
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    assert result["status"] == "cancelled"
    assert "not one of the three agents" in result["message"]
    assert "No answer within 24 hours" not in result["message"]


async def test_silence_says_so(no_children, monkeypatch):
    monkeypatch.setattr(agent_module.humanInput, "request", AsyncMock(return_value=None))
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    assert result["status"] == "cancelled"
    assert "No answer within 24 hours" in result["message"]


@pytest.mark.parametrize("blank", ["", "   ", {}, [], None])
async def test_an_empty_file_field_is_not_claimed_as_an_attachment(no_children, blank):
    """The ready reply must not claim to hold a document the user never attached."""
    result = await agent_module.orchestrator.fn({"brd_file": blank})
    no_children.assert_not_awaited()
    assert result["status"] == "ready"
    assert "document you attached" not in result["message"]


async def test_testcraft_explains_a_type_it_cannot_read(no_children, monkeypatch):
    """The file field accepts FitMap's .pdf, which TestCraft cannot read."""
    monkeypatch.setattr(
        agent_module.humanInput, "request", AsyncMock(return_value=_Answer("TestCraft"))
    )
    no_children.return_value = {
        "status": "success",
        "test_cases_document": {"file_key": "out/tests.xlsx"},
    }
    result = await agent_module.orchestrator.fn(
        {"start_workflow": True, "brd_file": "out/report.pdf"}
    )
    assert no_children.await_args.args[1] == {"generate": True}
    assert "was not used" in result["message"]
    assert "TestCraft does not read that file type" in result["message"]


@pytest.mark.parametrize("blank", ["", "   ", None, {}, []])
async def test_a_blank_start_point_falls_through_to_the_card(no_children, blank, ask):
    """The platform sends a blank for a dropdown left alone. Refusing one would stop
    the run instead of showing the card that exists to ask the question."""
    routed = AsyncMock(return_value={"status": "ready", "stage": "test", "message": "routed"})
    ask.return_value = _Answer("FitMap")
    import unittest.mock as _m

    with _m.patch.object(agent_module, "_run_from", routed):
        result = await agent_module.orchestrator.fn({"start_workflow": True, "start_from": blank})
    ask.assert_awaited_once()
    assert result["start_from"] == "FitMap"


@pytest.mark.parametrize("unsafe", ["../fitgap.xlsx", "https://example.com/f.xlsx", 17, {"k": "v"}])
async def test_an_unsafe_reference_is_refused_whichever_agent_receives_it(
    no_children, unsafe, monkeypatch
):
    """FitMap refused these and TestCraft used to drop them without a word. One check
    now covers both, so neither can disagree with the other about the same input."""
    for chosen, stage in (("FitMap", "fitgap"), ("TestCraft", "testcraft")):
        result = await agent_module.orchestrator.fn(
            {"start_workflow": True, "start_from": chosen, "brd_file": unsafe}
        )
        assert result["status"] == "invalid_input", (chosen, unsafe)
        assert result["stage"] == stage
    no_children.assert_not_awaited()


@pytest.mark.parametrize("action", ["cancel", "reject"])
async def test_a_cancelled_start_card_starts_nothing(no_children, ask, action):
    ask.return_value = _Answer("FitMap", action_type=action)
    result = await agent_module.orchestrator.fn({"start_workflow": True})
    no_children.assert_not_awaited()
    assert result["status"] == "cancelled"
    assert result["stage"] == "start"
    assert "You cancelled the start card" in result["message"]
    assert "start_from" not in result


async def test_the_start_card_carries_its_step_label(no_children, ask):
    ask.return_value = _Answer("BRDGen", action_type="cancel")
    await agent_module.orchestrator.fn({"start_workflow": True})
    assert ask.await_args.kwargs["metadata"] == {
        "title": "Where should this run start?",
        "step_label": "Choose agent",
    }
