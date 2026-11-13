"""Boundary checks for the existing TestCraft contract; no test generation here.

Sources, all read at AetherionAgents/explora_polaris commit 9e0eea7 (2026-10-29),
which is that repository's main and not the deployed build.
"""

from typing import Any

from src.agent.brd import is_storage_key

# src/agent/metadata.json (TestCraft 1.0.14): the `files` trigger accepts
# ".xlsx,.docx,.txt,.md". No .pdf, unlike FitMap's BRD input, so a PDF is never
# forwarded; TestCraft opens its own upload box for it instead.
TESTCRAFT_EXTENSIONS = (".xlsx", ".docx", ".txt", ".md")

# The only two statuses TestCraft returns from its registered function, in
# src/agent/agents.py: :512 on the single-document success path, :23 from
# `_cancelled` for a rejected or timed-out review gate, and :775 for a multi-document
# run, which is success when at least one document was produced and cancelled when
# none was. A child run's result is narrowed at :893 but never leaves the agent.
# An unknown status raises on purpose: stop and re-check rather than report an
# outcome this orchestrator has not seen.
_RESULT_STATUSES = ("success", "cancelled")


def build_testcraft_payload(document: Any) -> dict[str, Any]:
    """Start TestCraft and let it collect and check its own files.

    `generate` is TestCraft's own start flag (agents.py :815). A file is forwarded
    only when TestCraft accepts the type; with nothing usable it opens its own upload
    box (agents.py :899), the same way BRDGen collects its own inputs. `uploaded_files`
    is the first key TestCraft reads (agents.py :849) and the only one that is always
    a storage key rather than a display name.

    No task_metadata, customer_id or user_id: nothing in explora_polaris reads them.
    TestCraft's review cards reach the conversation through the child run record the
    platform creates for a bare uuid, which is what `_new_child_id` already provides.
    """
    child: dict[str, Any] = {"generate": True}
    if is_storage_key(document) and document.lower().endswith(TESTCRAFT_EXTENSIONS):
        child["uploaded_files"] = [document]
    return child


def validate_testcraft_result(result: Any) -> dict[str, Any]:
    """Do not advertise a workbook that TestCraft did not actually return."""
    if not isinstance(result, dict) or result.get("status") not in _RESULT_STATUSES:
        raise ValueError(
            "TestCraft returned an unrecognized result. Inspect its run before retrying."
        )
    documents = result.get("results", [])
    if not isinstance(documents, list) or not all(isinstance(item, dict) for item in documents):
        raise ValueError("TestCraft returned an invalid artifact list. Inspect its run.")
    if any("file_key" in item and not is_storage_key(item["file_key"]) for item in documents):
        raise ValueError("A TestCraft artifact is not a usable storage reference. Inspect its run.")
    workbook = result.get("test_cases_document")
    if workbook is not None:
        if not isinstance(workbook, dict) or not is_storage_key(workbook.get("file_key")):
            raise ValueError(
                "TestCraft's test_cases_document is not a usable storage reference. "
                "Inspect its run."
            )
    elif result["status"] == "success":
        raise ValueError("TestCraft reported success without a workbook. Inspect its run.")
    return result


def testcraft_artifacts(result: dict[str, Any]) -> list[dict[str, Any]]:
    """TestCraft's own download cards.

    `results` holds the combined workbook first and then one per document
    (agents.py :787); a single-document run returns the one workbook in both places
    (agents.py :514), so the flat field is the fallback rather than an addition.
    """
    documents = [item for item in result.get("results", []) if isinstance(item, dict)]
    if documents:
        return documents
    workbook = result.get("test_cases_document")
    return [workbook] if isinstance(workbook, dict) else []
