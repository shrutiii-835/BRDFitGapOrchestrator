# BRD-FitGap Orchestrator

Aetherion conversational agent coordinating the existing BRDGen and FitMap agents.

## Current behavior

The agent runs BRDGen, asks for an explicit Yes/No decision, and runs FitMap only on a Yes. Both are invoked through `agentExecutor` with their known input fields and platform metadata; the orchestrator waits for each child and returns its real artifacts, statuses and warnings. A `brd_file` input analyses an existing BRD directly, skipping generation and the consent card.

Child invocation uses a bare uuid workflow id, which is what lets the children's human-input cards register. The full chain is verified live on sbox/test, including FitMap's TestCraft offer and TestCraft's own cards.

## Local setup (macOS ARM64)

Requires Python 3.12, uv, and access to the official SDK host (VPN may be required).

```bash
cd orchestrator
uv sync --locked --python /opt/homebrew/bin/python3.12
source .venv/bin/activate
aetherion version
```

The SDK is pinned to 0.0.118, because 0.0.122 and above need database columns sbox-test lacks; `uv.lock` records resolved dependencies and hashes. The wheel targets macOS 26+ on ARM64. Do not use this wheel URL on Linux CI; an approved Linux source must be established first. If an old cached 403 persists after VPN access is restored, retry `uv sync --locked --no-cache`.

## Validation

From `orchestrator/`:

```bash
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/pytest -q
```

112 tests import the installed SDK and exercise the registered function, both boundary-check modules, the consent card and the FitMap handoff with mocked child execution, without starting platform runs. They do not prove conversation routing, authentication, or deployed end-to-end behavior; that is covered by the live sandbox runs.

## Files

All paths below are under `orchestrator/`.

- `src/agent/agent.py`: registered conversational entry point.
- `src/agent/schemas.py`: public input/output contract.
- `src/agent/brd.py`: input and output boundary validation for BRDGen.
- `src/agent/fitmap.py`: payload construction and result validation for FitMap.
- `tests/conftest.py`: supplies a plain logger, because the workflow logger needs a running workflow.
- `src/agent/prompts/conversation.md`: conversation and consent rules.
- `src/agent/metadata.json`: platform registration and form metadata.
- `src/tools/`: no custom activities; child invocation uses the SDK executor.
- `tests/`: input/intent and actual SDK registration checks.
