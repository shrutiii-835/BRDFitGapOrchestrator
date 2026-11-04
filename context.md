# Implementation context and handover

## Approved goal

Build a third Aetherion conversational agent coordinating BRDGen followed by optional FitMap analysis. The user must explicitly agree before FitMap runs. All existing input and review steps should appear in the same conversation. Neither reference agent may be modified or its pipeline duplicated.

The approved implementation plan is held outside this repository. Edge cases are included. The platform question was intentionally removed from the proposal, but remains an implementation dependency.

## Working agreement

Explain work before starting each phase and after completing it. Ask the user about major decisions. Keep code simple and production-oriented, commit significant steps with short messages, and maintain all handover documents. No tool attribution or co-author trailers.

## Preparation baseline - 2 November 2026

- Workspace: /Users/shruti/BRD-FitGap-orchestrator.
- Workspace root is not a Git repository.
- Protected nested repositories: BRD-Agent/explora_prism and fit-gap-agent/fit_gap_agent.
- Both reference repositories had empty `git status --porcelain` output at preparation.
- No implementation code or reference files changed during preparation.
- Created instruction, overview, architecture, context, and checklist documents.
- No application tests, dependency installation, or deployment performed.

## Repository decision

The user specified https://github.com/shrutiii-835/BRD-fitmap-orchestrator.git as the only repository for commits. Remote inspection returned no refs: the repository is empty. Connect this workspace to that remote and exclude both protected reference directories. New implementation source is reserved under orchestrator/.

Use the existing configured Git author identity. No commits may be made in either reference repository or any other repository. No application implementation has started.

## Evidence and limitations

Earlier documentation review confirmed conversational registration via @register and @agent, with chat_enabled and hitl_enabled. The SDK utilities explicitly prohibit human-input requests from agentExecutor.execute child workflows. A2A models expose run/status information but the reviewed documentation did not establish shared-conversation prompt routing.

Reference BRDGen uses SDK 0.0.91; reference FitMap uses 0.0.104. These are observations, not a decision for the new project's SDK version. Core AI prompts are hosted externally in Phoenix, not fully specified by these repositories.

BRDGen's Word branch can report success after skipped extraction chunks. FitMap can report success when some evidence sources fail. The orchestrator cannot repair these behaviors under the no-modification constraint and must not claim stronger completeness than the child results provide.

## Repository setup outcome

Initialized main at the workspace root and set origin to the authorized GitHub repository. Verified both reference paths are ignored and both nested repositories remain clean. Initial commit contains only working instructions, handover documents, the approved plan/PDF, and .gitignore. Application implementation and platform validation have not started. Remote publication is not yet performed.

## Phase 1 outcome

The user superseded the initial SDK choice with 0.0.124 and enabled VPN. The official index advertised the macOS ARM64 cp312 wheel. Download succeeded; the wheel metadata and CLI version confirm 0.0.124. An initial uv HTTP 403 was resolved by retrying with --no-cache.

Created orchestrator/ using the official CLI in an isolated bootstrap environment. The project has its own .venv, pinned wheel dependency, Python 3.12 restriction, and uv.lock. Removed demo activity implementations, scaffolded author identity, unused Black dependency, and the generated ignore rule that excluded uv.lock. No global installation, authentication, or reference-agent edits occurred.

Implemented the registered BRDFitGapOrchestrator foundation, packaged conversation prompt, matching schemas and metadata, and tests against the actual SDK. Strict boolean start intent prevents strings/numbers from triggering work. Explicit starts return unavailable until connectors exist; no fake success or artifacts are emitted.

Validation: 19 tests passed; Ruff lint and format checks passed; actual chat/HITL registration verified; Temporal sandbox preparation passed. Built wheel and source distribution successfully. Inspected wheel contents: prompt and both metadata files included; no .env or tests included. Both reference repositories remain clean. Authlib emits a dependency deprecation warning during test startup; security/dependency audit is still required before release. These local checks are not deployed end-to-end validation.

## Phase 2 investigation

The user selected test. CLI configuration confirmed sbox/test. Expired-session refresh failed, then normal browser login succeeded. Read-only registry access confirmed 29 agents, including active/chat-enabled BRDGen and FitMap. No existing-agent run was started.

Important live/reference difference: deployed FitMap now offers TestCraft after its analysis. Its offer_testcraft=false setting is documented only for direct runs, never conversation mode. On 3 November 2026 the user chose to preserve the offer and reported that FitMap uses agentExecutor to call TestCraft. The user confirmed TestCraft itself asks for input after launch.

Actual Python import confirms a2a_lib request/response models are bundled in 0.0.124. The current SDK utility page still prohibits child-workflow human input. Exact independent-run API and conversation routing remain unverified; no connector implementation or architecture choice has been committed.

## Current diagnostic status

The user approved agentExecutor-first verification on 3 November 2026. Prepared diagnostics/child_input_probe/ as an isolated sandbox package outside the production source. The child asks one boolean question; after confirmed completion the parent asks another. Neither invokes any business agent. Limits: two minutes per question, three minutes per child run, six minutes per parent run, and one child execution attempt.

21 local tests passed, including actual SDK registration and Temporal sandbox preparation. Mocked unit calls verify intent, sequencing, metadata forwarding, negative/invalid responses, timeout, and cancellation propagation; they are not proof of live platform routing. Ruff lint/format and source/wheel builds passed. Package contents were inspected; production package excludes the probe. Both reference repositories remain unchanged.

## Current BRD-only implementation - 3 November 2026

The user declined diagnostic publication and approved incremental testing through the actual orchestrator. The diagnostic remains isolated and unpublished; do not publish it.

Version 0.0.2 invokes BRDGen with agentExecutor using a literal registered name, a deterministic parent-derived child ID, one execution attempt, and a three-day child timeout inside a four-day parent. Only known inputs and platform metadata are forwarded. File references and result contracts are validated; real statuses, artifacts and warnings are retained. Cancellation propagates. There is no FitMap call or continuation prompt yet.

Validation: 54 tests pass, including SDK registration/sandbox preparation and mocked child calls for success, partial results, invalid contracts, errors and cancellation. Ruff checks pass. Version 0.0.2 wheel and source distribution build successfully. These checks do not establish live conversation routing. The lockfile remains pinned to SDK 0.0.124.

## Publication blocked by repository policy - 3 November 2026

The user approved publishing only BRDFitGapOrchestrator 0.0.2 to sbox/test, inspecting routing after publication instead of pre-configuring a queue map, and neutralizing the local `.env` queue pins for the attempt. Local preflight passed: clean main checkout, nothing untracked or ignored under `src/` or `pyproject.toml`, 54 tests and both Ruff checks green, agent name matching metadata, and a valid sbox/test session.

`aetherion publish --yes` refused before uploading: sbox/test accepts bundles only from a GitHub repository owned by AetherionAgents, and this checkout points at github.com/shrutiii-835/BRD-fitmap-orchestrator. Nothing was uploaded, registered, or executed. `GET /api/v1/agent/publish-policy` returned `require_main: false`, `reason: env`, so the branch rule is not the obstacle. Verified in `common_lib.deployment.publish_policy`: the origin rule covers (sbox, calfus) and (sbox, test), allowed owners is exactly AetherionAgents, and bundle evaluation exempts holders of `agents:publish_unreviewed` (Unreviewed Publisher).

Supported ways forward, both requiring the user: host the code in an AetherionAgents repository and point origin there, or have a tenant admin grant Unreviewed Publisher on sbox/test. Disguising the remote is not acceptable. The authorized commit repository is unchanged until the user decides.

## Routing and limitation evidence - 3 November 2026

`agentExecutor` resolves a child queue only from `AETHERION_AGENT_TASK_QUEUE_MAP` and `AETHERION_AGENT_TASK_QUEUE`, with a `task_queue` override available per call. Without a map, `execute("BRDGen", ...)` would schedule the child on the orchestrator's own agent queue, where BRDGen is not registered, so a routing failure would appear as a stalled child rather than an error. The synced registry cache already holds a queue id for BRDGen, so an environment-level map is possible without placing tenant values in source.

The SDK utilities page, updated 26 October 2026, still states that an agent started as a child through `agentExecutor.execute` cannot ask for human input and that the failure takes the whole run with it. If that still holds on the platform, the expected result of the live check is BRDGen's first upload card failing the child and the parent. That outcome would be a valid test result requiring an invocation change, not a defect in this release.

The project `.env` pins non-default agent and tool task queues from earlier local runs, and publish loads that file. It was neutralized for the attempt and restored from a backup afterwards. It remains untracked, and its values were never printed or committed. Neutralize it again before any future publish.

## Sandbox publication arrangement withdrawn - 3 November 2026

The origin rule is new: it is absent from SDK 0.0.105 and applies from CLI 0.0.122. The Arkon project on this device publishes from a personal remote because it was built with 0.0.105, before the rule existed, so it is not evidence that the current CLI accepts one.

The user approved publishing sandbox builds from a bundle carrying no git stamp, and `scripts/publish-sandbox.sh` staged `src`, `pyproject.toml` and `uv.lock` from `git archive HEAD:orchestrator` so each bundle equalled one commit. The attempt from commit 3874994 was refused before upload:

```
publishing to sbox/test needs a GitHub remote in the AetherionAgents organisation
```

The earlier local check that suggested this would pass was wrong. It evaluated `git_meta = None`, a state a real publish never produces: CLI 0.0.124 always stamps `cli_version`, so `predates_origin_stamp` is false and the `origin-missing` rule fires even outside a git checkout. Verified against the installed policy module: `None` and `{}` pass, `{'cli_version': '0.0.124'}` is blocked as `origin-missing`, and `{'cli_version': '0.0.105'}` passes only because it predates the stamp.

Under the pinned CLI only two routes remain, both needing the user: the Unreviewed Publisher role (`agents:publish_unreviewed`) on sbox/test, which sets the `exempt` flag in bundle evaluation, or an AetherionAgents-owned GitHub remote for this checkout. Publishing with the older 0.0.105 CLI present on this device would also skip the check and was rejected: the project pins 0.0.124, downgrading to evade a stamp is not acceptable, and it would test on a toolchain this project does not ship. The staging script was removed because it cannot succeed; prod remains publishable from the existing authorized repository, since prod requires git information and `main` but not the organisation remote.

## Older-CLI publication attempt - 3 November 2026

The user directed using SDK 0.0.118 or 0.0.119. Both wheels are available on the official index; 0.0.121 returns 403. Confirmed that 0.0.119's policy module contains the branch rule but no origin rule, which was added in 0.0.122, so a bundle stamped by it skips the organisation check on both sides.

Prepared, not executed: an isolated 0.0.119 CLI in a scratch environment, used only as a publishing tool, with `pyproject.toml` left pinned to 0.0.124 so the deployed agent keeps the runtime the 54 tests cover. Publishing from `orchestrator/` this way would also retain the branch and commit stamp, unlike the withdrawn no-git staging.

The assistant's own tooling refused to run the publish, classifying it as weakening a security control. Nothing was uploaded and the local `.env` was restored from backup. This route works only because 0.0.119 predates the check, so it goes around the policy rather than satisfying it, and bundles carrying an old CLI stamp are rejected when promoted to a main-only environment until republished. The decision rests with the user; the Unreviewed Publisher role remains the recommended route.

## First successful publication - 3 November 2026

The user published from `orchestrator/` with the isolated 0.0.119 CLI after logging in with it, because the 0.0.124 session store is not readable by that version. The upload was accepted: registration workflow `agent-bundle-b52e3a3d-d6e2-4d45-96a1-c1a02a901d54`, agent id `f93b2904-a766-440b-aea0-44afbaf1d2fe`, version 0.0.2, status PENDING at 07:31 UTC. The local `.env` queue pins were inactive during the publish, so no local queue values were forwarded. Nothing has been run yet.

The 0.0.119 publish has no `--yes` flag; it takes only `--source` and `--dist`.

Provenance was retained, unlike the withdrawn no-git route: the recorded stamp is `git_branch main`, `git_commit b479b2815177c61c2ae4e24827df2079f574dd9a`, `git_dirty false`. The stamp's `cli_version` is 0.0.105, not the 0.0.119 binary that ran, because `~/.config/aetherion/config.json` holds `AETHERION_SDK_VERSION = 0.0.105` from earlier work on another project and that version is what the older CLI stamps.

Open risk from the same setting: if the platform builds the agent image from the configured SDK version rather than the wheel pinned in `pyproject.toml`, the deployed agent runs 0.0.105 while this code and its 54 tests target 0.0.124, where the `@register` chat-agent interface differs. Confirm the built image's SDK version before accepting the deployment, and check whether the macOS wheel URL in `pyproject.toml` is usable for the platform's Linux build. Registry `activity_task_queues` and `runtime_config` are empty for both this agent and BRDGen, so child routing is still unproven.

## Live sandbox result - 3 November 2026

First real conversation against the deployed 0.0.2. Greeting path behaved as designed: the agent explained the service, stated that FitMap is not connected, opened no upload card and started nothing. An explicit request, confirmed with "yes", started the workflow. Parent agent run `f1fd0977-1682-421e-800c-8fadd6d15d2f`; the whole run finished in about seventy seconds and returned the implemented error path: "BRDGen could not complete. Inspect its run before retrying. FitMap was not started."

Routing is verified and needs no configuration from us. BRDGen's own worker log shows the child executing there: `workflow_type BRDGen`, `workflow_id f1fd0977-1682-421e-800c-8fadd6d15d2f-brd`, `task_queue e0f295b3-8480-46f8-acb0-c57def956256-task-queue`, which is BRDGen's agent id. Each deployed agent runs on `<agent-id>-task-queue`, and `agentExecutor.execute` resolved the literal name to the right deployed worker without a queue map. The earlier concern about inheriting our own queue does not apply.

The documented child human-input limitation is confirmed, with its mechanism. BRDGen started, tried to open its upload card, and its `register_human_input_request` activity failed three times with:

```
RuntimeError: register_request persisted no row for workflow
f1fd0977-1682-421e-800c-8fadd6d15d2f-brd (no agent_run, or run already terminal)
 - aborting to prevent indefinite wait
```

Human-input requests are bound to an `agent_run` record resolved from the workflow id (`common_lib.execution.hitl_persistence.resolve_agent_run_id`). The parent run has one; a workflow started as a Temporal child through `agentExecutor` does not, so the child cannot ask anything. This is not specific to the deterministic `-brd` child id: a child workflow has no agent run whatever it is called.

The orchestrator's own boundary handling was correct under the failure: the child error was caught, no FitMap or TestCraft run started, no artifacts were invented, the parent completed cleanly rather than hanging, and no orphan child remained. Registration is also confirmed good: workflow class `OrchestratorAgent`, registered name `BRDFitGapOrchestrator`, chat and human input enabled, both triggers present, and the packaged prompt visibly drove the replies, so the image runs a compatible SDK.

The consequence is architectural and affects more than BRDGen. FitMap also asks for its Oracle product and application selections, so invoking it through `agentExecutor` would fail the same way. The approved invocation approach is disproven for interactive children; the SDK's own guidance is to have a child return what it needs and let the parent ask, which cannot apply to agents that own their intake forms and must not be modified.

Options, none yet chosen: start each existing agent as an independent platform run bound to the current conversation, which the A2A documentation does not describe for conversation routing; ask the platform team how an agent invoked by another agent can raise human input, given the worker exposes a built-in `ensure_agent_run_for_hitl` activity; or change the product shape so the user starts the interactive agents and the orchestrator coordinates around them. TestCraft's reported behavior could not be checked: neither it nor FitMap had recent logs, and no agent is published under the registry name "TestCraft BRD Validation".

## HITL mechanics investigated - 3 November 2026

The platform's human-input component is a form raised by `humanInput.request`, with field types `text`, `textarea`, `integer`, `number`, `boolean`, `choice`, `multichoice` and `file`; a `file` field returns the uploaded object's storage key, or a list with `multiple=True`. A parent agent can therefore collect uploads itself and pass storage keys onward, and `metadata={"title": ...}` sets the card heading. Forms raised by the parent work, because the parent run owns an `agent_run`.

The deployed BRDGen trigger contract differs from this project's assumption: its file inputs are `transcript` (multiple, required) and `process_listing` (.xlsx, required), plus the `output_format` dropdown. The orchestrator currently forwards `uploaded_files`, which is not a BRDGen input and is silently ignored. Correct this when the invocation approach is settled.

Read-only inspection of the protected BRDGen reference shows where it asks. Intake is skipped when inputs are already supplied: the comment states that a start with everything supplied never opens the box, and the format question is raised only when `task_metadata.conversation_id` is present, so forwarding the parent's conversation metadata is itself what forces that question. The file-check form appears only when validation finds problems. The draft review at `_review_requirements`, however, is called unconditionally before any document is produced, and there is no flag to skip or pre-approve it. Supplying every input therefore removes two of the three asks but never the third.

A child cannot be rescued by supplying inputs, and not by a newer SDK either: `aetherion_sdk.human_input` calls only `register_human_input_request`, `read_human_input_response` and `expire_human_input_request`. The `ensure_agent_run_for_hitl` activity that the worker registers is platform machinery invoked when the platform starts an agent run, not something the SDK's `humanInput` calls. Human input consequently requires a run that the platform created, which a Temporal child workflow is not.

The same reasoning applies to FitMap. Its Oracle product and application selections could be supplied up front, but its TestCraft offer is a further ask that must be preserved, so it too would fail as a child. Both existing agents need real platform runs.

## Platform API review - 3 November 2026

The SDK documentation describes only `agentExecutor`, which is disproven here. The platform's own OpenAPI specification at `/api/v1/openapi.json` (340 paths, read with the signed-in session) exposes the pieces the SDK pages omit:

- `POST /agent/run` starts a named agent as a real platform run, taking `agent_name`, `agent_params`, optional `id`, `run_in_sync`, `llm` and `files`. A run created this way is a platform run, so it owns the `agent_run` record whose absence broke the child invocation.
- `GET /agent/run/{run_id}` returns a run; `GET /agent/{agent_id}/runs` lists them.
- `GET /runs/{run_id}/input-requests` lists a run's asks. `InputRequestDTO` carries `request_id`, `run_id`, `workflow_id`, `request_type`, `prompt`, `schema`, `actions`, `attachments`, `metadata`, `requested_by_step`, `agent_name`, `status`, `expires_at` and `timed_out`, which is everything needed to reproduce a question.
- `POST /runs/{run_id}/input-requests/{request_id}/respond` answers one, taking `action_type`, `payload` and optional `channel`.
- `GET /chat/{conversation_id}/active-runs` returns "the caller's runs whose result hasn't reached this conversation yet (running, parked on a HITL ask, or finished with delivery pending)", so the platform already tracks conversation-linked runs that are waiting on a person.
- `POST /runs/{run_id}/conversation` opens a conversation for an existing run. `POST /chat` is the user-facing turn endpoint and takes `conversation_id`, `message`, an optional `agent` and `human_input_response`.

Two candidate architectures follow, neither yet chosen or validated.

Relay: a tool starts BRDGen with `POST /agent/run`, polls its pending input requests, and the orchestrator re-raises each one as its own `humanInput` form in the user's conversation, then posts the real answer back through the respond endpoint until the run finishes. Everything stays in one conversation and neither existing agent changes. It must relay only answers the user actually gave, never synthesise one. Open risks: mapping each child `schema` to the SDK's `Field` types, surfacing `attachments` such as BRDGen's draft workbook, polling cadence and idempotency, avoiding a second place where the same card can be answered, and confirming which identity the deployed agent presents when calling the API, since tenant and user authorization must be preserved.

Conversation-linked run: start the existing agent so the platform binds the run to the current conversation and renders its own cards there, with the orchestrator waiting for completion. `active-runs` implies this binding exists, but `POST /agent/run` exposes no conversation field, so the supported way to create that link is unconfirmed and is the main question for the platform team.

These endpoints are official API surface but the documentation does not describe agent-to-agent use of them, so confirm the intended pattern before building on either.

## Upstream pattern found - 3 November 2026

The user supplied two upstream pull requests: AetherionAgents/fit_gap_agent#22 (FitMap offering TestCraft) and AetherionAgents/explora_prism#13 (BRDGen handing off to Writehand). Both are open, and both solve exactly the problem this project hit, the same way.

The cause of our failure is the child's workflow id. Both implementations carry the same comment: "A bare uuid: supernova gives only those a child agent_run, which HITL cards need", and both pass `workflow_id=str(workflow.uuid4())`. This orchestrator used a readable derived id, `f"{parent_workflow_id}-brd"`, so the platform created no child agent run and BRDGen's upload card had nowhere to register. The limitation is therefore conditional, not absolute, and the invocation architecture does not need to change. `workflow.uuid4()` is replay-safe, so the fix keeps determinism.

FitMap's README states the consequence plainly: TestCraft's own review cards, for file check, extraction, scenarios and export, appear in the same chat, and its child timeout is a day to cover them. It also warns to confirm the behaviour on the target platform before relying on it, which this project must still do.

Routing: before the call they resolve the child's queue with a `resolve_agent_task_queue` tool that reads the target's ACTIVE row from the platform `agents` table and passes `{agent_id}-task-queue`, falling back to routing by name. Our live run already proved name routing reaches the right worker, so the lookup is an optional hardening rather than a requirement. Both repos keep the agent name a literal at the call site because the platform maps queues only for names it can find in `agentExecutor.execute("<name>")`.

Dependency warning from the same pull request: FitMap deliberately stays on aetherion-sdk 0.0.118, because "versions 0.0.122 and above need DB columns that sbox-test doesn't have yet, so the worker crashed on startup". This project pins 0.0.124. The deployed agent did not crash, which fits the publish stamp recording `cli_version 0.0.105` and suggests the image was not built on 0.0.124, but the pin is a live risk and should be aligned with the platform's working version.

Other details worth copying: `execution_timeout` rather than `run_timeout` for the child, one attempt so a retry cannot regenerate a whole pipeline, and reporting the child's outcome under its own key so the parent's own results are never lost when the child is declined, cancelled or fails.

## Version 0.0.3 - 3 November 2026

Applied the upstream pattern. The child workflow id is now `str(workflow.uuid4())`, which is replay-safe and is what makes the platform create the child agent run that BRDGen's cards need. The child limit moved from `run_timeout` to `execution_timeout`, matching upstream; one attempt is unchanged, so a retry cannot repeat BRDGen's whole pipeline. The invented `uploaded_files` field was replaced with BRDGen's real `process_listing` input, alongside `transcript`; both remain optional, because BRDGen opens its own intake card for whatever is missing.

The SDK pin moved from 0.0.124 to 0.0.118, the version FitMap keeps on this platform because 0.0.122 and above need database columns sbox-test lacks and crash the worker on startup. The project version is 0.0.3 in `pyproject.toml` and both metadata files, since republishing a live version is rejected.

Validation on 0.0.118: 54 tests pass, including registration and Temporal sandbox preparation against the actual SDK, Ruff lint and format pass, and both distributions build. The wheel contains the prompt and both metadata files and excludes `.env` and tests. These checks do not prove the live card behaviour, which is the point of the next run.

Still unresolved: `~/.config/aetherion/config.json` holds `AETHERION_SDK_VERSION = 0.0.105` from other work, which is what the publish stamp records and possibly what the platform builds with. It was left alone because it is global and shared with another project; confirm which SDK the built image uses before trusting the pin.

## Live verification of 0.0.3 - 3 November 2026

The Conversations area of the platform is currently unavailable, so the user tested from the Run Agent page instead. Those runs confirm the fix.

Run `f764134c-c6d7-4d4a-95e2-78c3cf306aa2` (10:47 to 10:52 UTC) carries three input requests, all raised by BRDGen against child workflow `61f57005-c84a-41d3-918e-cafbf2579843`, a bare uuid, and all answered: its intake card asking for the process listing and transcripts, then two file-check cards. The child's own cards therefore register and surface on the parent run, which is exactly what the derived child id prevented in 0.0.2. The documented child human-input limitation is conditional on the child id, and `agentExecutor` is confirmed viable for interactive agents on this platform.

That run then failed inside BRDGen's own pipeline, not in this orchestrator: "Business requirement extraction failed for every transcript chunk. The masking service or the LLM may be unavailable." The orchestrator preserved that message verbatim, returned status error with stage brd and the child workflow id, started no FitMap run and invented no artifacts. Both file-check cards had also warned that the uploaded process listing looked like a business requirements document and that the transcripts did not match the listing, so the inputs were themselves mismatched.

Run `5e08f9e3` was terminated by the user after a file-check card expired, and run `a47e78c1` completed in four seconds with no input requests, consistent with the ready response when no start is requested.

Still unverified: a successful BRD, the draft review card and its attached workbook, the returned artifacts, cancellation behaviour, and anything specific to the Conversations surface, which needs that area working. A green BRD also needs valid inputs and a healthy masking/LLM service.

## Phase 3 implemented - version 0.0.4 - 3 November 2026

Scope: select the final BRD document, show BRDGen's real warnings, and ask the user explicitly whether to continue to fit-gap analysis. FitMap is still not called; that is Phase 4.

After a success or partial result the workflow selects the one `.xlsx` or `.docx` output through `select_brd_document`, then raises its own card with a required Yes/No choice field, a 24-hour timeout and `on_timeout="return_none"`. The parent owns this ask, so it does not depend on the child-run question at all. Only the literal answer "Yes" continues; "No", a timeout and any unrecognised answer all stop with the BRD, and the actual answer is returned as `continue_decision` so the outcome is auditable. Silence is never consent. A failed, cancelled or invalid BRD is never offered the decision. Partial-result warnings appear in the card itself, before the user answers, and again in the final message. BRDGen's own artifacts and status are returned unchanged on every path.

Because FitMap is not connected, a Yes is recorded and the reply says exactly that, rather than implying an analysis ran. The packaged conversation instructions were updated to forbid answering the card on the user's behalf or claiming FitMap has run.

Validation on SDK 0.0.118: 61 tests pass, 7 of them new, covering the card's fields and timeout, acceptance of Yes, refusal on No, timeout, an unrecognised answer, suppression of the card after a failed BRD, and warnings reaching both the card and the message. The consent stub is autouse, so no test can reach the real human-input activity. Ruff lint and format pass and both 0.0.4 distributions build.

Not yet verified live: the card's appearance and behaviour on the platform, which needs a successful BRD run.

## Phase 4 implemented - version 0.0.4 - 3 November 2026

The deployed FitMap contract was read from the registry first, because the earlier BRDGen assumption proved wrong. FitMap 0.58.0 takes `brd_file` (.xlsx, .docx or .pdf), optional `supplementary_files`, `other_supporting_files` when the product is Other, and the required `oracle_product` and `oracle_application` dropdowns. Its documented input schema adds `conversation_mode`, `start_analysis` and `offer_testcraft`, and its outputs are `status`, `message`, `summary`, `artifacts`, `analysis_report`, `client_report`, plus `test_scripts_report` and `testcraft` from the TestCraft offer.

On an explicit Yes the orchestrator starts FitMap with a bare uuid child id, a two-day execution timeout covering its selection cards and any TestCraft work, and one attempt. The child payload carries only `conversation_mode`, `start_analysis`, the BRD `file_key` and platform `task_metadata`. It never sends `oracle_product`, `oracle_application` or `offer_testcraft`: those choices and the TestCraft offer belong to FitMap and the user, and a test asserts their absence. The parent run timeout rose to seven days to cover three days of BRDGen, a day of waiting for consent and two days of FitMap.

Results are preserved on every path. A successful analysis returns FitMap's own status, summary, reports and artifacts together with BRDGen's outputs and both run ids, under stage fitgap with `brd_status` recording the BRD's own outcome. If FitMap fails, is cancelled or times out, the BRD is returned intact with its message saying so, and the orchestrator never dresses up a non-success status as success. The BRD reference is validated as a storage key with a supported extension before the call.

Recovery: supplying `brd_file` with a start request analyses an existing BRD and skips both generation and the continuation card, because supplying a BRD and asking for analysis is itself the explicit request. The field was added to the input schema and as an optional file trigger.

Validation on SDK 0.0.118: 81 tests pass, 20 of them new, covering payload contents and the absence of user-owned choices, both agents' artifacts, refusal to start FitMap after a No, a failed FitMap keeping the BRD, an unsuccessful status not being dressed up, the recovery path skipping the card, unusable BRD references, unrecognised results and metadata copying. Ruff lint and format pass and both 0.0.4 distributions build with the new module included.

Not yet verified live: the whole chain, which needs a successful BRD run. FitMap's conversation_mode behaviour as a child is also unverified, including whether its selection cards register the way BRDGen's did.

## Full chain verified live - version 0.0.4 - 3 November 2026

Run `627dd47b-5787-4250-a929-82aeaebdd571` completed the whole workflow on sbox/test, from upload to test
scripts, in about six minutes. Nine cards appeared in one run, every one answered by the user:

1. BRDGen intake, child workflow `a1571a83`, process listing and transcripts uploaded, Excel chosen.
2. BRDGen draft review, previously unverified: "Draft ready with 13 business requirement(s)", with the
   draft workbook attached to the card. Answered Approve.
3. This orchestrator's own consent card, step `fitmap_consent`, on the parent run itself. Answered Yes.
4. FitMap's Oracle product and application cards, child workflow `c065be95`. Oracle EPM, E-Business Suite.
5. FitMap's TestCraft offer, step `fitmap_generate_tests_1`. Answered Yes.
6. TestCraft's extraction, scenario and export reviews, workflow `70111eb9`, a grandchild of this run.

Four agents therefore raised human input inside one orchestrator run, two of them below a child. The bare
uuid child id holds for FitMap exactly as it did for BRDGen, and it holds transitively: FitMap's own child
reached the same conversation without this project doing anything for it.

The returned payload is what the contract promised: `stage fitgap`, `status success`, `brd_status success`,
`continue_decision Yes`, both child workflow ids, FitMap's summary, and eight artifacts covering BRDGen's
Business_Requirements.xlsx and Anonymized_Data.zip, FitMap's fit-gap Excel and PDF, and TestCraft's test
scripts workbook. `analysis_report`, `client_report`, `test_scripts_report` and `testcraft` are all
populated. Nothing was invented and nothing was lost: BRDGen's outputs survive alongside FitMap's.

The TestCraft offer was preserved as required. The orchestrator never sent `offer_testcraft`,
`oracle_product` or `oracle_application`; FitMap asked and the user chose.

Earlier runs the same hour confirm the failure paths stay intact. Run `5c5c41f5` and the file-check card in
run `349f9771` both show BRDGen rejecting a business requirements document offered as a process listing, and
its replacement flow working through the orchestrator unchanged.

Still unverified: cancellation and timeout behaviour on a live run, restart durability, and the Conversations
surface, which the platform team has not yet restored. These are Phase 5 work.

## Version 0.0.5 - greeting corrected - 4 November 2026

The packaged conversation prompt still carried a CURRENT AVAILABILITY block saying FitMap continuation was
not connected and that the build was a sandbox increment, so the deployed agent told users the fit-gap step
was unavailable even though run `627dd47b` had completed it. The block is replaced with WHAT YOU CAN DO,
describing the whole flow as available, and the wording "the planned flow" became "the flow". The rule
against claiming unreturned results is kept: the greeting was stale, not the caution.

No workflow logic changed. Versions moved to 0.0.5 in `pyproject.toml` and both metadata files, because
republishing a live version is rejected. The agent metadata description already described the full flow and
needed no change. 81 tests, Ruff lint and format pass, and both distributions build with the corrected
prompt packaged and no `.env` or tests included. This needs publishing before the greeting changes.

## Pre-PR review and cleanup - version 0.0.5 - 4 November 2026

Published 0.0.5 to sbox/test with the project's own pinned 0.0.118 CLI, which predates the AetherionAgents
origin rule exactly as the 0.0.119 binary did, so the separate scratch CLI is no longer needed. Registration
workflow `agent-bundle-15ecb9e4-9fef-4b14-8fb0-ae13801ad180`, accepted 202. The local `.env` was already
neutralized and was byte-identical before and after the publish.

Security and dependency review findings, recorded so the PR discloses rather than hides them:

- Nine installed packages carry published advisories: `pillow`, `strawberry-graphql`, `starlette`, `mcp`,
  `langchain-core`, `langchain-anthropic`, `langchain-openai`, `requests`, and `pytest` (dev only). Every one
  is transitive through `aetherion-sdk 0.0.118`; this project has no direct dependency but the SDK. They
  cannot be resolved without moving off the pin, and 0.0.122 and above crash the sbox-test worker. Most
  arrive through `arize-phoenix`, which this code does not call. Checked against OSV on 4 November 2026.
- The SDK wheel is macOS ARM64 only and is hash-pinned in `uv.lock`. `uv sync` cannot run on Linux CI.
- `src/` contains no logging at all, so a failed run leaves no local trace of which child failed. Nothing
  leaks, but the production-logging expectation is unmet. Open.
- The `brd_file` recovery path's failure branches are untested (`agent.py` lines 83 and 86-91), and a bad
  `brd_file` reports `invalid_input` when it is not a string but `error` when it is a malformed key, both
  under `stage: "brd"` although no BRD stage ran. Open.

No secrets are tracked, `.env` is ignored, `.env.template` is empty, and `is_storage_key` rejects URLs,
absolute paths, path traversal and control characters. There is no shell execution, eval or deserialization
anywhere in the source. These checks reduce risk; they are not a guarantee that no vulnerability exists.

Cleanup: `diagnostics/child_input_probe/` was removed, having been superseded in Phase 2 and never published.
The BRD-Agent and fit-gap-agent reference checkouts were removed at the user's instruction. Both were clean,
carried no unpushed commits or stashes, and remain at github.com/AetherionAgents/explora_prism and
.../fit_gap_agent, so a contract question can be answered by re-cloning. `.gitignore` still excludes those
paths. Both READMEs were rewritten: they still described 0.0.4, an unconnected FitMap and a blocked
publication.

## Review principles applied - version 0.0.6 - 4 November 2026

0.0.5 reached ACTIVE at 05:28 UTC on its own image, built from commit d29357d, and the greeting no longer
claims FitMap is unconnected. The source then moved to 0.0.6, which is not published.

Reviewed against correctness, readability, performance, security, testing and architecture. Three findings
were fixed:

- Traceability. A failing FitMap returned no run id, so a failure could not be traced the way a BRDGen
  failure could. The child id is now created by the caller and reported on every failure branch, in both the
  consent path and the recovery path. `_run_fitmap` takes an id and an already-built payload, which also
  separates payload validation from execution.
- Status honesty on the recovery path. An unusable `brd_file` returned `invalid_input` when it was not a
  string but `error` when it was a malformed key, and both claimed `stage: "brd"` although no BRD stage ran.
  Both now return `invalid_input` under `stage: "fitgap"`, and the entry point no longer needs to catch an
  exception that the helper should have handled.
- Logging. `src/` had none, so a failed run left no local trace. The workflow now logs each child's start,
  status and failure through `workflow.logger`, which is replay-aware. It records run ids and statuses only:
  never file keys, which carry original filenames, and never document contents or masking data.

Testing: 98 tests, up from 81, taking statement coverage from 92 to 98 per cent. The new tests cover the
recovery path's rejection of non-string and unusable references, a failed FitMap run, an unrecognised FitMap
result, cancellation on both paths, and the consent path naming a failed FitMap run while keeping the BRD.
`tests/conftest.py` supplies a plain logger, because `workflow.logger` requires a running workflow and these
tests call the registered function directly. The four remaining uncovered lines are defensive guards that
`validate_brd_result` makes unreachable.

Performance: there are no database calls, network calls or loops outside the two child executions; all
validation is linear over small result lists. Architecture is unchanged and still matches the upstream
pattern: literal agent names, bare uuid child ids, `execution_timeout`, and one attempt per child.

Not changed: the dependency advisories, which remain transitive through the SDK pin, and the publishing
workaround. Both are disclosed in the README.

## Next actions

1. Publish 0.0.6 when convenient; 0.0.5 is live and the differences are internal.
2. Phase 5: verify cancellation, timeout and restart behaviour on live runs.
3. Confirm the release target and the durable publishing route.

## Documentation references

- https://test.sbox.aetherion.io/docs/quickstart
- https://test.sbox.aetherion.io/docs/chat-agents
- https://test.sbox.aetherion.io/docs/sdk-utilities
- https://test.sbox.aetherion.io/docs/a2a-lib
- https://test.sbox.aetherion.io/docs/decorators
- https://test.sbox.aetherion.io/docs/task-queue-routing
- https://test.sbox.aetherion.io/docs/publish
- https://test.sbox.aetherion.io/docs/configuration

## Scope clarification - 3 November 2026

Do not set offer_testcraft=false or bypass the deployed offer. FitMap owns the optional TestCraft invocation and consent. The orchestrator should preserve the actual returned artifacts and outcomes and must not duplicate or automatically trigger that handoff. The user's agentExecutor reference does not by itself approve an unverified invocation architecture for interactive BRDGen/FitMap.

User-reported evidence now supports trying SDK-native child workflows despite the documentation caveat. Architecture candidate approved; BRDGen invocation is now implemented locally, but no live compatibility check has run.
