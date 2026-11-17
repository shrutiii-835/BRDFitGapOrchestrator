# BRD-FitGap Orchestrator

Aetherion conversational agent coordinating the existing BRDGen, FitMap and TestCraft agents. A run begins at whichever of the three the user picks and goes forward from there, one agent at a time. The choice comes from a `start_from` input when one is supplied, and otherwise from a card the workflow raises before anything starts; an attached document never answers it, because FitMap and TestCraft both accept one. Each agent keeps its own intake and reviews, so starting at any of them works without supplying anything up front, and a document the chosen agent cannot read is explained rather than forwarded or silently dropped.

From BRDGen the orchestrator asks an explicit Yes/No before running FitMap, and asks nothing after that: FitMap raises its own TestCraft offer, which this agent neither answers nor suppresses. Children are invoked through `agentExecutor` under a bare uuid workflow id, which is what lets their human-input cards register, and are reached by name — no task-queue lookup is needed. The orchestrator returns each child's real artifacts, statuses and warnings, never its internal failure text. Verified live on sbox/test: the start-point card, starting at FitMap, starting at TestCraft, and the BRDGen-to-FitMap chain including FitMap's TestCraft offer.

## Local setup (macOS ARM64)

Requires Python 3.12, uv, and access to the official SDK host (VPN may be required).

```bash
cd orchestrator
uv sync --locked --python /opt/homebrew/bin/python3.12
source .venv/bin/activate
aetherion version
```

The SDK is pinned to 0.0.118, because 0.0.122 and above need database columns sbox-test lacks; `uv.lock` records resolved dependencies and hashes. The wheel targets macOS 26+ on ARM64 and is built against CPython 3.12, which is why `requires-python` excludes 3.13. Do not use this wheel URL on Linux CI; an approved Linux source must be established first. If an old cached 403 persists after VPN access is restored, retry `uv sync --locked --no-cache`.

## Validation

From `orchestrator/`:

```bash
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/pytest -q
```

206 tests exercise the registered function, all three boundary-check modules, the start-point card, the BRDGen consent card and the FitMap and TestCraft handoffs with mocked child execution, without starting platform runs. Coverage is 98%, with a 95% floor enforced by `--cov-fail-under`. They do not prove conversation routing, authentication, or deployed end-to-end behavior; that is covered by the live sandbox runs.

CI (`.github/workflows/unit_test.yml`) runs the same lint and tests on a public `ubuntu-latest` runner. The SDK is private and ships no Linux wheel, so `tests/conftest.py` stubs it there and the two tests that assert on the real SDK's registration skip themselves and say so.

## Files

All paths below are under `orchestrator/`.

- `src/agent/agent.py`: registered conversational entry point; owns the start-point card and the BRDGen-to-FitMap consent.
- `src/agent/schemas.py`: public input/output contract, including `start_from`.
- `src/agent/brd.py`: input and output boundary validation for BRDGen.
- `src/agent/fitmap.py`: payload construction and result validation for FitMap.
- `src/agent/testcraft.py`: payload construction, result validation and artifacts for TestCraft.
- `src/agent/prompts/conversation.md`: conversation, card and ownership rules.
- `src/agent/metadata.json`: platform registration and form metadata.
- `src/tools/`: no custom activities; child invocation uses the SDK executor.
- `tests/conftest.py`: supplies a plain logger, because the workflow logger needs a running workflow, and stubs the SDK when it is not installed.
- `tests/`: input/intent, start-point, handoff and SDK registration checks.
