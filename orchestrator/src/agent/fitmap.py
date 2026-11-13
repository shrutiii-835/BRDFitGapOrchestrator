"""Boundary checks for the existing FitMap contract; no analysis logic here."""

from typing import Any

from src.agent.brd import is_storage_key

_RESULT_STATUSES = ("success", "error", "cancelled", "timeout", "invalid_input", "ready")
_DOCUMENTS = ("analysis_report", "client_report", "test_scripts_report")
BRD_EXTENSIONS = (".xlsx", ".docx", ".pdf")


def build_fitmap_payload(brd_file_key: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    """Hand FitMap the BRD and let it collect its own Oracle choices.

    conversation_mode keeps FitMap's existing selection cards and its TestCraft
    offer. offer_testcraft is never sent: it is a direct-run override, and the
    offer belongs to FitMap and the user.

    None means no document was supplied, and the key is left out so FitMap opens its
    own upload card: its intake asks for the BRD first and skips that step only when
    one is already valid (AetherionAgents/fit_gap_agent, src/agent/workflow.py on
    branch feature/fitmap-testcraft, :174 and :202). A key that was supplied but is
    unusable is still refused rather than passed on.
    """
    if brd_file_key is not None and (
        not is_storage_key(brd_file_key) or not brd_file_key.lower().endswith(BRD_EXTENSIONS)
    ):
        raise ValueError("The BRD reference is not a usable .xlsx, .docx or .pdf storage key.")
    child: dict[str, Any] = {
        "conversation_mode": True,
        "start_analysis": True,
    }
    if brd_file_key is not None:
        child["brd_file"] = brd_file_key
    metadata = payload.get("task_metadata")
    if isinstance(metadata, dict):
        child["task_metadata"] = dict(metadata)
    return child


def validate_fitmap_result(result: Any) -> dict[str, Any]:
    """Do not report analysis that FitMap did not actually return."""
    if not isinstance(result, dict) or result.get("status") not in _RESULT_STATUSES:
        raise ValueError("FitMap returned an unrecognized result. Inspect its run before retrying.")
    values = result.get("artifacts", [])
    if not isinstance(values, list) or not all(isinstance(item, dict) for item in values):
        raise ValueError("FitMap returned an invalid artifact list. Inspect its run.")
    for name in _DOCUMENTS:
        document = result.get(name)
        if document is None:
            continue
        if not isinstance(document, dict) or not is_storage_key(document.get("file_key")):
            raise ValueError(f"FitMap's {name} is not a usable storage reference. Inspect its run.")
    return result


def fitmap_artifacts(result: dict[str, Any]) -> list[dict[str, Any]]:
    """FitMap's own artifacts, including any TestCraft outcome it chose to return."""
    artifacts = [item for item in result.get("artifacts", []) if isinstance(item, dict)]
    if artifacts:
        return artifacts
    return [result[name] for name in _DOCUMENTS if isinstance(result.get(name), dict)]
