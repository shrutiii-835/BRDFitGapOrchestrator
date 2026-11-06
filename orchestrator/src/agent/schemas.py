"""Public conversation contract; platform-owned file/context fields stay separate."""

AGENT_NAME = "BRDFitGapOrchestrator"

INPUT_SCHEMA = [
    {
        "name": "start_workflow",
        "type": "boolean",
        "required": False,
        "description": "True only when the user explicitly asks to start BRD generation.",
    },
    {
        "name": "output_format",
        "type": "string",
        "required": False,
        "description": "Excel or Word, only when explicitly selected by the user.",
    },
    {
        "name": "brd_file",
        "type": "file",
        "required": False,
        "description": (
            "An existing BRD to analyse directly, skipping generation. Only when the user "
            "supplies one and asks for fit-gap analysis."
        ),
    },
]

OUTPUT_SCHEMA = [
    {
        "name": "status",
        "type": "string",
        "description": (
            "ready, success, partial, cancelled, invalid_input, or error; applies to the BRD stage."
        ),
    },
    {
        "name": "message",
        "type": "string",
        "description": "Actual outcome or next-step explanation.",
    },
    {"name": "artifacts", "type": "array", "description": "Conversation-visible result artifacts."},
    {
        "name": "stage",
        "type": "string",
        "description": "brd or fitgap, whichever stage the run reached.",
    },
    {
        "name": "continue_decision",
        "type": "string",
        "description": (
            "Yes, No, or timeout; the user's actual answer to the continuation question."
        ),
    },
    {
        "name": "brd_workflow_id",
        "type": "string",
        "description": "Child run identifier for tracing.",
    },
    {"name": "outputs", "type": "array", "description": "Original BRDGen output artifacts."},
    {
        "name": "fitmap_workflow_id",
        "type": "string",
        "description": "FitMap run identifier for tracing, when FitMap ran.",
    },
    {
        "name": "brd_status",
        "type": "string",
        "description": "BRDGen's own status, preserved when FitMap ran afterwards.",
    },
    {"name": "summary", "type": "string", "description": "FitMap's own fit/gap summary."},
    {
        "name": "analysis_report",
        "type": "object",
        "description": "FitMap's Excel analysis artifact.",
    },
    {"name": "client_report", "type": "object", "description": "FitMap's PDF report artifact."},
    {
        "name": "test_scripts_report",
        "type": "object",
        "description": "TestCraft's workbook, when FitMap's own offer was accepted.",
    },
    {
        "name": "testcraft",
        "type": "object",
        "description": "FitMap's TestCraft outcome, returned unchanged when it was offered.",
    },
    {
        "name": "warning",
        "type": "string",
        "description": "Original partial-extraction warning.",
    },
    {
        "name": "consolidation_warning",
        "type": "string",
        "description": "Original consolidation warning.",
    },
    {
        "name": "skipped_files",
        "type": "array",
        "description": "BRDGen's own list of input files it could not use.",
    },
    {
        "name": "used_despite_issues",
        "type": "array",
        "description": "BRDGen's own list of input files accepted despite reported issues.",
    },
    {
        "name": "skipped_chunk_count",
        "type": "number",
        "description": "Transcript chunks BRDGen could not extract requirements from.",
    },
    {
        "name": "process_row_count",
        "type": "number",
        "description": "Process rows BRDGen read from the listing.",
    },
    {
        "name": "process_ids_with_requirements",
        "type": "number",
        "description": "Processes BRDGen produced requirements for.",
    },
    {
        "name": "masked_entity_count",
        "type": "number",
        "description": "Entities BRDGen's masking service replaced.",
    },
    {
        "name": "consolidated_from",
        "type": "number",
        "description": "Requirement count before BRDGen consolidated duplicates.",
    },
]


# The OUTPUT_SCHEMA fields above whose values come from BRDGen, not FitMap.
#
# On the FitMap-success path the result is built from FitMap's own dict, so anything
# BRDGen set is overwritten unless it is carried forward explicitly. Declaring the set
# here, beside the schema that promises it, keeps the two together: a new BRD-owned
# field added above belongs in this tuple as well, and a test fails if they drift.
#
# Sources, all read at AetherionAgents/explora_prism commit 0cbc8ea, src/agent/agent.py.
# Most are conditional, so this is what the orchestrator may carry, not what every run
# returns:
#   :607, :648  process_row_count, masked_entity_count - always, both branches
#   :649        process_ids_with_requirements - Excel branch only
#   :670, :672  skipped_files, used_despite_issues - only when inputs had problems
#   :674, :676  skipped_chunk_count, warning - only when extraction partly failed
#   :681, :685  consolidation_warning or consolidated_from - mutually exclusive
# The Word branch returns at :628 with only the two counts, so a Word BRD carries no
# diagnostics at all. An absent field is left absent rather than carried as null: a
# caller can then tell "BRDGen reported nothing skipped" from "BRDGen never looked".
#
# FitMap returns no field of any of these names - in AetherionAgents/fit_gap_agent
# (commit 2c1fe69) every "warning" is a logger call - so carrying them overwrites
# nothing of FitMap's.
BRD_RESULT_FIELDS = (
    "warning",
    "consolidation_warning",
    "skipped_files",
    "used_despite_issues",
    "skipped_chunk_count",
    "process_row_count",
    "process_ids_with_requirements",
    "masked_entity_count",
    "consolidated_from",
)
