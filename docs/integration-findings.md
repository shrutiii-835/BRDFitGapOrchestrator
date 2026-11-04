# Phase 2 integration findings

## Scope and current state

The user confirmed `sbox / test` for integration checks. This investigation is read-only with respect to deployed agents: neither existing agent was invoked, published, or changed.

The expired browser session could not refresh. Normal `aetherion login --env sbox --tenant test` completed successfully. No credentials or tokens are recorded in the repository.

`aetherion sync --dry-run agents` reached the registry and found 29 agent entries. Note the option order: the SDK requires --dry-run on the sync group, before agents. The command wrote no cache/stubs. The observed endpoint is https://test.sbox.aetherion.io/api/v1/registry.

## Deployed contracts

Targeted read-only registry inspection confirmed:

| Agent | State | Contract observations |
|---|---|---|
| BRDGen | Active, chat enabled | generate_brd and output_format inputs; status, outputs and artifacts results match the reference. |
| FitMap | Active, chat enabled | Core BRD/product/application inputs remain, but the deployed agent additionally offers TestCraft. |

FitMap has an `offer_testcraft` input. Its description explicitly allows false only for direct runs and says never to set it in conversation mode. Its output contract adds `test_scripts_report` and `testcraft`; artifacts may contain TestCraft results. This behavior is absent from the protected local reference.

Do not silently suppress the offer with an unsupported conversation parameter, automatically consent to TestCraft, or assume that receiving a FitMap report means its complete workflow has ended. The user confirmed that the existing TestCraft offer must be preserved. FitMap remains responsible for that offer and its consent handling; the orchestrator must not suppress it, start TestCraft itself, or provide consent on the user's behalf. Return FitMap's actual artifacts, including any optional TestCraft outcome, without regenerating them.

## SDK and documentation verification

- [SDK utilities](https://test.sbox.aetherion.io/docs/sdk-utilities) still explicitly prohibit human-input requests in agentExecutor.execute child workflows.
- [A2A documentation](https://test.sbox.aetherion.io/docs/a2a-lib) describes typed requests and responses, but the reviewed material does not establish same-conversation routing or the exact invocation endpoint.
- Python imports confirm `a2a_lib.models.A2ARequest`, `A2AResponse`, and the agent-card helper are available in SDK 0.0.124. A filesystem-only search missed the compiled packaging; do not interpret that as a missing package.
- A2ARequest exposes correlation_id, idempotency_key, agent_id, skill, input_data, callback_url, ttl_seconds and metadata.
- A2AResponse exposes correlation_id, status, workflow_id, sse_endpoint, status_endpoint, result, message and timestamp.
- The registry entries inspected expose no invocation definition (definition is null). A registry entry is not sufficient evidence of an HTTP invocation or conversation-routing contract.

## Decisions and evidence needed before connector implementation

1. Scope decision resolved: preserve FitMap's existing optional TestCraft offer.
2. The user reports that FitMap calls TestCraft with agentExecutor. The user confirms TestCraft itself asks for human input after invocation. This contradicts or narrows the documented restriction; verify the same behavior for this orchestrator before relying on it.
3. Verify authentication/authorization, run creation, idempotency, status retrieval, and correlation of human-input cards and replies.
4. Present the concrete invocation/routing approach to the user for approval.
5. Implement only after those contracts are verified; then test in the sandbox without modifying either reference agent.

The Phase 1 foundation remains unchanged and intentionally returns unavailable for a start request. Phase 2 is not complete.

## Follow-up decision - 3 November 2026

The existing FitMap-to-TestCraft offer is now explicitly in scope for preservation, not reimplementation. The user identifies agentExecutor as the invocation mechanism used there. This is useful evidence of child-agent execution but does not yet resolve the documented child human-input limitation. The user subsequently confirmed that TestCraft itself asks after invocation. No unsupported relay, child invocation, or API connector has been added.

## Proposed verification path

The user approved SDK-native agentExecutor as the preferred approach, subject to sandbox verification. First verify in the sandbox that a child-owned input card appears in the parent conversation, its answer resumes the correct child, the parent remains waiting until child completion, and cancellation/timeout do not leave an orphan run. Check existing BRDGen upload and draft-review behavior before considering the connector complete. Preserve FitMap's existing TestCraft offer and nested outcomes.

These are acceptance checks, not observed results. Do not mark the documented limitation resolved solely from the user-reported example. The user selected incremental testing through the actual orchestrator; neither reference agent is to be changed.

## Prepared diagnostic

An isolated publishable project is available at diagnostics/child_input_probe/. It defines OrchestrationInputProbe and OrchestrationInputProbeChild. The parent invokes the child once, the child asks a boolean question, and only a confirmed child response allows the parent to ask its own boolean question. Each question expires in two minutes; child and parent execution limits are three and six minutes respectively. It copies platform-supplied task_metadata without inventing correlation fields. Whether this is sufficient is explicitly unverified.

Local checks: 21 tests passed with actual SDK registration/sandbox preparation and mocked execution/input calls for logic tests. Ruff lint/format passed. Both distributions built; wheel inspection confirmed source and metadata included, no .env/tests included. The production orchestrator package excludes this diagnostic. Reference repositories remain clean. No live compatibility result is claimed.

Superseded: the user declined diagnostic publication and approved testing through the actual orchestrator instead. Do not publish this diagnostic. Version 0.0.2 implements BRDGen-only invocation; see brd-sandbox-check.md for the pending deployment and acceptance checks. User acceptance of agentExecutor as a candidate does not by itself establish platform compatibility. The existing BRDGen, FitMap, and TestCraft must not be invoked or changed by this probe.
