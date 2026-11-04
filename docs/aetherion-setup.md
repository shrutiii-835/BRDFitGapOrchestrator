# Aetherion setup and Phase 1 verification

## Verified local prerequisites

Checked on 2 November 2026:

| Item | Result |
|---|---|
| Architecture | arm64 |
| macOS | 27.0.1 |
| Python | /opt/homebrew/bin/python3.12, version 3.12.14 |
| uv | 0.12.15 |
| aetherion CLI on PATH | Not found |

Use a project-local Python 3.12 virtual environment. Do not modify system Python or either reference project's environment.

## Approved SDK and installation

The user selected SDK 0.0.124 and enabled VPN access. The official index then advertised this exact wheel:

https://sdk.sbox.aetherion.io/Darwin/aetherion_sdk-0.0.124-cp312-cp312-macosx_26_0_arm64.whl

Downloaded and inspected the wheel metadata, installed it in an isolated bootstrap environment, and verified `aetherion version` reports 0.0.124. Created `orchestrator/` with the official `aetherion init orchestrator` command. The project uses its own `.venv` and a committed `uv.lock`.

Earlier index/installer/0.0.104 attempts returned HTTP 403 before VPN access. An initial uv request also returned 403 after the successful 0.0.124 download; `uv sync --no-cache` resolved it. Do not downgrade SDK versions to work around access errors. No global installer was executed and no reference environment was modified.

The project restricts Python to >=3.12.10,<3.13 because the selected wheel is cp312. The scaffold's uv.lock ignore rule was removed to retain reproducibility. Ruff supplies both linting and formatting; the unused scaffolded Black dependency was removed.

## Current documentation findings

- [CLI](https://test.sbox.aetherion.io/docs/cli): use `aetherion init <project>` for scaffolding; `aetherion run` starts the combined worker; `aetherion publish` publishes the combined agent/tools package.
- [Project structure](https://test.sbox.aetherion.io/docs/project-structure): use `src/agent/` and `src/tools/`, pinned platform-compatible SDK dependency, Python >=3.12.10,<3.13, and a committed `uv.lock`. The displayed 0.0.55 wheel is an example, not a release lookup.
- [Chat agents](https://test.sbox.aetherion.io/docs/chat-agents): use `@register` outside `@agent`, `type="agent"`, `chat_enabled=True`, and `hitl_enabled=True`. The older `@chat_agent` interface is removed.
- macOS wheel URLs cannot simply be reused on Linux CI. Confirm an approved Linux package source before enabling SDK-dependent CI there.

The installed SDK accepts the documented registration flags. Registration and sandbox preparation were checked locally; deployed conversation behavior is not yet verified.

## Phase 1 scope

Create the new project under `orchestrator/`, using the documented layout and the approved SDK. Define the conversational entry point, prompt, input/output schemas, and matching registration metadata. Keep integration work for the subsequent phases; no placeholder workflow may report successful BRD or FitMap execution.

The conversation must recognize explicit start intent, avoid launching on a greeting or attachment alone, and never invent file references, analysis results, or user consent. Final artifact data comes from actual existing-agent results.

## Phase 1 acceptance checks

- SDK version and Python compatibility verified inside the new environment.
- Dependencies resolve reproducibly and the lockfile is committed.
- Agent imports and registration are verified against the actual SDK.
- Prompt, schemas, and metadata agree on the public contract.
- Relevant lint, format, and tests pass without modifying reference agents.
- Documentation clearly distinguishes a scaffold from working integration.

Local registration, input tests, workflow-sandbox preparation, and package resource inspection have run. See context.md for the final verification outcome. No remote workflow has run.

## Authentication and deployment

The supplied notes contain both `test` and `calfus` tenant names. Confirm the correct target before login or publication. Use `aetherion login`, not the typographical `agwnaetherion login`. Do not print `aetherion config list` indiscriminately because configuration may contain secrets. Do not delete environments or lockfiles as a routine upgrade step; make deliberate, reproducible dependency updates.
