"""Public conversation contract; platform-owned file/context fields stay separate."""

AGENT_NAME = "BRDFitGapOrchestrator"

# The agents this orchestrator can begin a run at, in the order they chain. Each one
# runs forward from where it starts; the agent after it is offered, never assumed.
START_POINTS = ("BRDGen", "FitMap", "TestCraft")

INPUT_SCHEMA = [
    {
        "name": "start_workflow",
        "type": "boolean",
        "required": False,
        "description": "True only when the user explicitly asks to start a run.",
    },
    {
        "name": "start_from",
        "type": "string",
        "required": False,
        "description": (
            "BRDGen, FitMap or TestCraft; the agent to begin at. Set it only when the "
            "user names one. The run asks for the choice when it is absent."
        ),
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
            "An existing BRD or Fit-Gap document, used by whichever agent the run starts "
            "at: FitMap analyses it, TestCraft generates tests from it. Only when the "
            "user supplies one."
        ),
    },
]

OUTPUT_SCHEMA = [
    {
        "name": "status",
        "type": "string",
        "description": (
            "ready, success, partial, cancelled, invalid_input, or error; the outcome of "
            "the last agent the run reached."
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
        "description": (
            "start, brd, fitgap or testcraft, whichever stage the run reached; start "
            "means it stopped before any agent ran."
        ),
    },
    {
        "name": "start_from",
        "type": "string",
        "description": "BRDGen, FitMap or TestCraft; the agent this run actually began at.",
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
        "name": "test_cases_document",
        "type": "object",
        "description": "TestCraft's own workbook, when the run started at TestCraft.",
    },
    {
        "name": "testcraft_workflow_id",
        "type": "string",
        "description": "TestCraft run identifier for tracing, when the run started there.",
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
]


# The OUTPUT_SCHEMA fields above whose values come from BRDGen, not FitMap.
#
# On the FitMap-success path the result is built from FitMap's own dict, so anything
# BRDGen set is overwritten unless it is carried forward explicitly. Declaring the set
# here, beside the schema that promises it, keeps the two together: a new BRD-owned
# field added above belongs in this tuple as well, and a test fails if they drift.
#
# Sources, all read at AetherionAgents/explora_prism commit 0cbc8ea, src/agent/agent.py.
# All four are conditional, so this is what the orchestrator may carry, not what every
# run returns:
#   :670, :672  skipped_files, used_despite_issues - only when inputs had problems
#   :676        warning - only when extraction partly failed
#   :681        consolidation_warning - only when consolidation failed
# The Word branch returns at :628 before any of them are set, so a Word BRD carries
# none. An absent field is left absent rather than carried as null: a caller can then
# tell "BRDGen reported nothing skipped" from "BRDGen never looked".
#
# BRDGen also returns counts (process_row_count, masked_entity_count and the rest).
# They are deliberately left out. They describe BRDGen's own processing rather than the
# result this orchestrator returns, and every name in OUTPUT_SCHEMA is a promise to keep
# returning it, so mirroring another agent's internal counters would tie this contract
# to that agent's implementation. The warnings and the skipped-file lists are the part a
# consumer can act on.
#
# FitMap returns no field of any of these names - in AetherionAgents/fit_gap_agent
# (commit 2c1fe69) every "warning" is a logger call - so carrying them overwrites
# nothing of FitMap's.
BRD_RESULT_FIELDS = (
    "warning",
    "consolidation_warning",
    "skipped_files",
    "used_despite_issues",
)
