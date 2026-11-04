"""Exercise the foundation against the installed SDK, without starting remote runs."""

import json
from importlib import resources

import pytest
from aetherion_sdk.decorators import AGENT_REGISTRY, REGISTERED_TOOLS
from temporalio import workflow
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner

from src.agent.agent import orchestrator
from src.agent.schemas import AGENT_NAME, INPUT_SCHEMA


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


async def test_registered_workflow_can_be_prepared_in_temporal_sandbox():
    definition = AGENT_REGISTRY[AGENT_NAME]
    SandboxedWorkflowRunner().prepare_workflow(
        workflow._Definition.must_from_class(definition.temporal_class)
    )
