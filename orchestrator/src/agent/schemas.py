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
]
