"""Exercise the foundation against the installed SDK, without starting remote runs."""

import json
import tomllib
from datetime import timedelta
from importlib import import_module, resources
from pathlib import Path

import aetherion_sdk
import pytest
from aetherion_sdk.decorators import AGENT_REGISTRY, REGISTERED_TOOLS
from temporalio import workflow
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner

from src.agent.agent import orchestrator
from src.agent.schemas import AGENT_NAME, INPUT_SCHEMA

agent_module = import_module("src.agent.agent")

# These two assert on the SDK's own registration, so a stub could only confirm what the
# stub was written to do. On a runner without the private SDK they skip and say so,
# rather than passing for the wrong reason. conftest installs the stub.
needs_real_sdk = pytest.mark.skipif(
    getattr(aetherion_sdk, "__stub__", False),
    reason="needs the real aetherion_sdk; the stub cannot prove platform registration",
)


@pytest.mark.parametrize(
    "payload", [{}, {"start_workflow": False}, {"process_listing": ["a.xlsx"]}]
)
async def test_no_explicit_start_remains_idle(payload):
    result = await orchestrator.fn(payload)
    assert result["status"] == "ready"
    assert result["artifacts"][0]["text"] == result["message"]


@pytest.mark.parametrize("start", ["true", "false", 1, 0, None, [], {}])
async def test_non_boolean_start_is_rejected(start):
    result = await orchestrator.fn({"start_workflow": start})
    assert result["status"] == "invalid_input"


@pytest.mark.parametrize("payload", [None, [], "start", {"output_format": "PDF"}])
async def test_invalid_input_returns_safe_error(payload):
    assert (await orchestrator.fn(payload))["status"] == "invalid_input"


@needs_real_sdk
def test_real_sdk_registration_and_metadata_agree():
    definition = AGENT_REGISTRY[AGENT_NAME]
    registration = REGISTERED_TOOLS[AGENT_NAME]
    metadata = json.loads(resources.files("src.agent").joinpath("metadata.json").read_text())
    assert definition.name == metadata["name"] == AGENT_NAME
    assert registration.chat_enabled is True
    assert registration.runtime_config["hitl_enabled"] is True
    assert metadata["config"]["hitl_enabled"] is True
    assert registration.input_schema == INPUT_SCHEMA
    assert {field["name"] for field in INPUT_SCHEMA} == {
        field["name"] for field in metadata["config"]["triggers"]
    }


@needs_real_sdk
async def test_registered_workflow_can_be_prepared_in_temporal_sandbox():
    definition = AGENT_REGISTRY[AGENT_NAME]
    SandboxedWorkflowRunner().prepare_workflow(
        workflow._Definition.must_from_class(definition.temporal_class)
    )


def test_the_run_cap_is_never_reached_by_the_stages():
    """The cap is uncatchable: it must outlast every path a run can take, or a healthy
    run is killed with no result. Strictly greater, so setting _SLACK to zero fails
    here. Both paths begin with the start question, so both include it."""
    brd_chain = (
        agent_module._START_TIMEOUT
        + agent_module._BRD_TIMEOUT
        + agent_module._CONTINUE_TIMEOUT
        + agent_module._FITMAP_TIMEOUT
    )
    testcraft_path = agent_module._START_TIMEOUT + agent_module._TESTCRAFT_TIMEOUT
    assert agent_module._RUN_TIMEOUT > brd_chain
    assert agent_module._RUN_TIMEOUT > testcraft_path


def test_the_run_cap_covers_the_longest_path_and_no_more():
    """The cap is the start question plus the longest chain after it, plus slack.

    It grew from 8 days to 10 when FitMap's timeout was raised to its own 4-day
    limit, which is the derivation working: a longer stage lengthens the cap by
    exactly the difference. Starting at TestCraft is an alternative to the BRDGen
    chain, never an addition, so the cap takes the longer of the two rather than
    their sum.
    """
    assert agent_module._RUN_TIMEOUT == timedelta(days=10)
    assert agent_module._RUN_TIMEOUT == (
        agent_module._START_TIMEOUT
        + agent_module._BRD_TIMEOUT
        + agent_module._CONTINUE_TIMEOUT
        + agent_module._FITMAP_TIMEOUT
        + agent_module._SLACK
    )
    # The TestCraft path is shorter, so it must not add to the cap.
    assert agent_module._TESTCRAFT_TIMEOUT < agent_module._BRD_CHAIN


def test_the_two_version_numbers_agree():
    """The platform reads [project].version in pyproject.toml, not metadata.json, and
    refuses a publish whose version is already live. Bumping one and not the other
    means a publish is rejected, or worse, succeeds under the wrong number."""
    metadata = json.loads(resources.files("src.agent").joinpath("metadata.json").read_text())
    pyproject = tomllib.loads(
        (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
    )
    assert pyproject["project"]["version"] == metadata["version"]


@needs_real_sdk
def test_start_card_sends_options_as_a_plain_list_so_the_chat_renders_a_selection():
    """The SDK's default spec sends ``[{"value": ...}]``, which the chat does not draw
    as selectable options. FitMap's cards send a plain list and render as a numbered
    selection, so the start card must send the same shape."""
    field = agent_module._ChoiceField(
        name="start_from",
        type="choice",
        friendly_name="Start from",
        options=agent_module.START_POINTS,
        required=True,
    )
    spec = field.to_field_spec()
    assert spec["name"] == "start_from"
    assert spec["options"] == ["BRDGen", "FitMap", "TestCraft"]


@needs_real_sdk
def test_continue_card_sends_yes_no_as_a_plain_list():
    """The BRD-to-FitMap consent card uses the same selection shape as the start card."""
    field = agent_module._ChoiceField(
        name="continue_to_fitmap",
        type="choice",
        friendly_name="Continue to fit-gap analysis",
        options=("Yes", "No"),
        required=True,
    )
    assert field.to_field_spec()["options"] == ["Yes", "No"]
