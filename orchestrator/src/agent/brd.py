"""Small boundary checks for the existing BRDGen contract; no document processing."""

from typing import Any


def is_storage_key(value: Any) -> bool:
    """Accept object keys, never URLs, local paths, or path traversal."""
    return (
        isinstance(value, str)
        and bool(value.strip())
        and not value.startswith(("/", "\\"))
        and ":" not in value
        and "\\" not in value
        and not any(ord(char) < 32 or ord(char) == 127 for char in value)
        and not any(part in (".", "..") for part in value.split("/"))
    )


def build_brd_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Forward only known BRD inputs and platform context, without mutating them."""
    child: dict[str, Any] = {"generate_brd": True}
    metadata = payload.get("task_metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise ValueError("Platform task_metadata must be an object.")
        child["task_metadata"] = dict(metadata)
    # BRDGen's own inputs; it opens its intake card for whatever is missing.
    for name in ("transcript", "process_listing"):
        values = payload.get(name)
        if values is None:
            continue
        if not isinstance(values, list) or not all(is_storage_key(key) for key in values):
            raise ValueError(f"{name} must be a list of uploaded file storage keys.")
        child[name] = list(values)
    output_format = payload.get("output_format")
    if output_format is not None:
        child["output_format"] = output_format
    return child


def validate_brd_result(result: Any) -> dict[str, Any]:
    """Do not advertise completion when the child returned an invalid contract."""
    if not isinstance(result, dict) or result.get("status") not in (
        "success",
        "partial",
        "cancelled",
        "invalid_input",
        "error",
    ):
        raise ValueError("BRDGen returned an unrecognized result. Inspect its run before retrying.")
    for field in ("outputs", "artifacts"):
        values = result.get(field, [])
        if not isinstance(values, list) or not all(isinstance(item, dict) for item in values):
            raise ValueError("BRDGen returned an invalid artifact list. Inspect its run.")
        if any("file_key" in item and not is_storage_key(item["file_key"]) for item in values):
            raise ValueError(
                "A BRDGen artifact is not a usable storage reference. Inspect its run."
            )
    if result["status"] in ("success", "partial"):
        documents = [
            item
            for item in result.get("outputs", [])
            if item.get("extension") in ("xlsx", "docx")
            and item.get("type") == "s3_download_link"
            and is_storage_key(item.get("file_key"))
            and item["file_key"].lower().endswith(f".{item['extension']}")
        ]
        # BRDGen returns exactly one requirements document, by construction.
        # AetherionAgents/explora_prism, src/agent/agent.py, commit 0cbc8ea (2026-10-14):
        # the outputs list is built in two places only, the arms of one
        # `if output_format == "word"` branch at line 581 -
        #   line 609: one .docx + one masking .zip
        #   line 651: one .xlsx + one masking .zip
        # Both are hard-coded literals; nothing appends and nothing loops, so Word and
        # Excel can never both appear. (The third .xlsx, at line 399, is a draft attached
        # to a review card, not an output.)
        # That is a read of that repository's main, not of the deployed build. If BRDGen
        # ever returns two documents, this raises on purpose: stop and re-verify rather
        # than silently sending FitMap a file nobody chose.
        if len(documents) != 1:
            raise ValueError(
                "BRDGen did not return one final requirements document. Inspect its run."
            )
    return result


def select_brd_document(result: dict[str, Any]) -> dict[str, Any]:
    """Return the final requirements document; validate_brd_result guarantees one."""
    for item in result.get("outputs", []):
        if (
            item.get("extension") in ("xlsx", "docx")
            and item.get("type") == "s3_download_link"
            and is_storage_key(item.get("file_key"))
        ):
            return item
    raise ValueError("BRDGen returned no usable requirements document. Inspect its run.")


def brd_notices(result: dict[str, Any]) -> list[str]:
    """Actual warnings from the child, never softened or summarised."""
    return [
        result[field]
        for field in ("warning", "consolidation_warning", "error")
        if isinstance(result.get(field), str) and result[field].strip()
    ]
