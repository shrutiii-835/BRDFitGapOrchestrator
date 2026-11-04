# BRD-FitGap Orchestrator

An Aetherion conversational agent that runs BRDGen, asks whether to continue, and passes the final BRD to FitMap after explicit consent.

## Current status

Phases 1 to 4 are complete and verified live on sbox/test. The agent runs BRDGen, asks an explicit Yes/No continuation question, and then runs FitMap, preserving its Oracle selections and its TestCraft offer.

Version 0.0.5 is deployed on sbox/test. The source is at 0.0.6, which adds workflow logging, traceable FitMap run ids on failure, and corrected statuses on the recovery path; it is not published yet.

Run `627dd47b-5787-4250-a929-82aeaebdd571` completed the whole chain on 3 November 2026: BRDGen's intake and draft review, this agent's consent card, FitMap's Oracle selections and TestCraft offer, and TestCraft's own three review cards, all in one conversation, returning both agents' artifacts. See [sandbox checklist](docs/brd-sandbox-check.md), [project setup](orchestrator/README.md), and [integration findings](docs/integration-findings.md).

Phase 5 remains: cancellation, timeout and restart verification, and the release decision.

## Workspace

- `docs/orchestrator-implementation-plan.md`: approved implementation plan.
- `output/pdf/orchestrator-implementation-plan.pdf`: shareable plan.
- `context.md`: decisions, evidence, and continuation notes.

Publishing to sbox/test normally requires a GitHub remote owned by AetherionAgents. This project publishes with the pinned 0.0.118 CLI, which predates that rule, so it is a workaround rather than a satisfied policy. A durable fix needs either the Unreviewed Publisher role on sbox/test or an AetherionAgents remote. See context.md.

Repository: https://github.com/shrutiii-835/BRD-fitmap-orchestrator.git. This workspace is its local checkout; agent source lives in `orchestrator/`, and its README documents the verified local and publish commands.

The BRDGen and FitMap source repositories were kept here as read-only references and have been removed now that the integration is verified. They remain at github.com/AetherionAgents/explora_prism and .../fit_gap_agent if a contract question needs checking again; `.gitignore` still excludes those paths so a re-clone stays untracked.

## Scope

Keep all interaction in one conversation. Reuse existing input and review forms. Transfer a stored document reference rather than downloading and re-uploading the BRD. Preserve the BRD if the user declines or FitMap fails. Do not duplicate either agent's processing logic.

## Setup status

See [Aetherion setup](docs/aetherion-setup.md) for verified prerequisites, the installed SDK version and the resolved access issue. The agent is deployed on sbox/test as `BRDFitGapOrchestrator`.

## Official references

- [Quickstart](https://test.sbox.aetherion.io/docs/quickstart)
- [Chat agents](https://test.sbox.aetherion.io/docs/chat-agents)
- [SDK utilities and human input](https://test.sbox.aetherion.io/docs/sdk-utilities)
- [Agent-to-agent interface](https://test.sbox.aetherion.io/docs/a2a-lib)
