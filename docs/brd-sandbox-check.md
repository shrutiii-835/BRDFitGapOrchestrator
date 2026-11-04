# BRD-only orchestrator sandbox check

## Approved approach

Use the actual orchestrator for incremental testing. The separate diagnostic agents are not to be published. This sandbox release is version 0.0.2 of BRDFitGapOrchestrator and invokes only the existing BRDGen through agentExecutor.

Publishing or running this release has not yet been approved. Do not treat the user's approval of the approach as proof that the platform supports the flow.

## What the release does

- Requires explicit start_workflow=true before invoking anything.
- Calls the fixed registered name BRDGen, never a target chosen from user input.
- Forwards generate_brd=true plus available transcript, uploaded_files, output_format and task_metadata fields. It does not invent a conversation identifier.
- Uses a deterministic child ID derived from the parent workflow ID, a three-day child timeout, and no whole-child retry. Parent timeout is four days for this BRD-only increment.
- Preserves BRDGen's existing upload, validation, and draft-review behavior.
- Returns the actual result status, document/archive artifacts, and warnings. Rejects malformed or unusable final document references instead of claiming success.
- Does not invoke FitMap or TestCraft, and does not ask the continuation question yet.

## Routing preflight

After approval to publish, verify the target environment is sbox and tenant is test. Confirm the new registration is BRDFitGapOrchestrator version 0.0.2. Confirm BRDGen resolves to its own deployed worker via the supported AETHERION_AGENT_TASK_QUEUE_MAP/routing configuration, not the new orchestrator queue. The literal BRDGen name in the executor call is available to SDK source-reference discovery.

No tenant-specific queue names, tokens, or user IDs are hardcoded. Correct registration and routing must be observed before executing the workflow.

## Live acceptance steps

Use non-sensitive sample inputs. A person must answer the actual upload and review cards; the implementation must not manufacture consent.

1. Open one conversation with BRDFitGapOrchestrator and explicitly request BRD generation.
2. Confirm BRDGen's input card appears in that same conversation. If it does not, inspect run state and stop; do not create repeated runs to hide the failure.
3. Upload a process listing and transcript, then choose Excel.
4. Confirm the child reaches draft review in that same conversation and the parent remains active while waiting.
5. Review the draft and approve it. Confirm the reply resumes the correct child.
6. Confirm the parent returns the real BRD artifacts and any warnings, with stage=brd and the child run ID.
7. Confirm no FitMap or TestCraft run was started, and no early child completion event incorrectly closes or hides the parent.
8. In a separate controlled run, cancel at intake/review; verify there is no downstream run. Check parent cancellation and orphan-child behavior before accepting cancellation support.

Word, replacement uploads, and restart/replay behavior need follow-up checks. Local mocked tests do not prove those platform behaviors. Deterministic child IDs protect replay within one parent run; cross-run duplicate user requests remain a later reliability task.

## Outcomes

Not executed remotely. Record actual run IDs, observations, failures, and next actions in context.md without committing uploaded private content or credentials.

## Publication attempt - 3 November 2026

Approved by the user: publish only BRDFitGapOrchestrator 0.0.2 to sbox/test, keep diagnostics unpublished, inspect routing after publication rather than pre-configuring a queue map, and neutralize the local queue pins in `orchestrator/.env` for the attempt.

Preflight passed: session valid for sbox/test against https://test.sbox.aetherion.io/api/v1, working tree clean on main, no untracked or ignored files under `src/` or `pyproject.toml`, 54 tests and both Ruff checks passing, and the registered `@agent` name matching `metadata.json`.

`aetherion publish --yes` authenticated, read `GET /api/v1/agent/publish-policy` (`require_main: false`, `reason: env`), and then stopped before uploading:

```
Blocked by publish policy:
  - publishing to sbox/test is allowed only from a repository in the AetherionAgents GitHub organisation
    (current remote: github.com/shrutiii-835/BRD-fitmap-orchestrator)
```

Nothing was uploaded, registered, or run. The local `.env` was restored from its backup immediately afterwards; it is untracked and its queue values were never printed or committed.

The rule is in `common_lib.deployment.publish_policy`: `ORIGIN_RULE_TENANTS` covers `(sbox, calfus)` and `(sbox, test)`, `REMOTE_HOSTS` is GitHub only, and `ALLOWED_REMOTE_OWNERS` is exactly `AetherionAgents`. The main-branch rule does not apply here, because sbox/test is in `FEATURE_BRANCH_TENANTS`. The bundle evaluation accepts an `exempt` flag tied to `agents:publish_unreviewed`, the Unreviewed Publisher role a tenant admin grants under Admin to Access.

Do not point this checkout at a repository we do not own, and do not otherwise disguise the origin to satisfy the check. The supported options are an AetherionAgents-owned remote or the Unreviewed Publisher role on sbox/test. This is a deployment and repository decision for the user; the authorized commit repository is unchanged in the meantime.

## Second publication attempt - 3 November 2026

The user approved publishing a bundle staged outside the checkout so it would carry no git stamp. `scripts/publish-sandbox.sh` staged commit 3874994 and the CLI refused before upload with `origin-missing`: sbox/test needs a GitHub remote in the AetherionAgents organisation. Nothing was uploaded.

CLI 0.0.124 always stamps `cli_version`, so a bundle built outside a git checkout is still judged by the origin rule rather than skipped. The script was removed. Publication now waits on the Unreviewed Publisher role or an AetherionAgents remote.
