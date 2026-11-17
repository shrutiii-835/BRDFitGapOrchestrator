"""Shared test setup; no platform calls are made.

The real `aetherion_sdk` is private, so a public CI runner cannot install it. When it
is missing, this installs a small stub before anything imports `src`, which lets the
behaviour tests run anywhere. The two tests that assert on the real SDK's own
registration skip themselves instead of asserting against the stub - a stub can only
confirm what it was written to do, never what the platform does.
"""

import logging
import sys
import types
from importlib import import_module

import pytest


def _install_sdk_stub() -> None:
    """Enough of the SDK's surface for the agent module to import and run."""
    sdk = types.ModuleType("aetherion_sdk")
    sdk.__stub__ = True
    decorators = types.ModuleType("aetherion_sdk.decorators")
    decorators.__stub__ = True
    decorators.AGENT_REGISTRY = {}
    decorators.REGISTERED_TOOLS = {}

    class Field:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class _AgentDefinition:
        def __init__(self, fn, name, run_timeout):
            self.fn = fn
            self.name = name
            self.run_timeout = run_timeout
            self.temporal_class = None

        async def __call__(self, *args, **kwargs):
            return await self.fn(*args, **kwargs)

    def agent(*, name=None, run_timeout=None, **_):
        def wrap(fn):
            definition = _AgentDefinition(fn, name, run_timeout)
            decorators.AGENT_REGISTRY[name] = definition
            return definition

        return wrap

    def register(**_):
        return lambda fn: fn

    async def _unused(*_args, **_kwargs):  # pragma: no cover - tests patch these
        raise AssertionError("A test reached the SDK stub; patch the call instead.")

    executor = types.SimpleNamespace(execute=_unused)
    human_input = types.SimpleNamespace(request=_unused)

    sdk.Field = Field
    sdk.agent = agent
    sdk.register = register
    sdk.agentExecutor = executor
    sdk.humanInput = human_input
    sdk.decorators = decorators
    sys.modules["aetherion_sdk"] = sdk
    sys.modules["aetherion_sdk.decorators"] = decorators


try:  # The installed SDK is always preferred; the stub is only a CI fallback.
    import aetherion_sdk  # noqa: F401

    REAL_SDK = True
except ImportError:  # pragma: no cover - only taken on a runner without the SDK
    _install_sdk_stub()
    REAL_SDK = False


agent_module = import_module("src.agent.agent")


@pytest.fixture(autouse=True)
def workflow_logger(monkeypatch):
    """The workflow logger needs a running workflow; these tests call the function
    directly, so supply a plain logger that records to the test run instead."""
    monkeypatch.setattr(agent_module.workflow, "logger", logging.getLogger("test.orchestrator"))
