"""Shared test setup; no platform calls are made."""

import logging
from importlib import import_module

import pytest

agent_module = import_module("src.agent.agent")


@pytest.fixture(autouse=True)
def workflow_logger(monkeypatch):
    """The workflow logger needs a running workflow; these tests call the function
    directly, so supply a plain logger that records to the test run instead."""
    monkeypatch.setattr(agent_module.workflow, "logger", logging.getLogger("test.orchestrator"))
