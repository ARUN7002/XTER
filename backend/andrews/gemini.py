"""Constrained Gemini website interaction adapter for Phase 5.

The default mode is manual transfer. No credentials, cookies, browser handles,
or website automation are accepted by this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable


class GeminiError(RuntimeError):
    pass


class GeminiUnavailable(GeminiError):
    pass


class GeminiIncomplete(GeminiError):
    pass


class TransferMode(StrEnum):
    MANUAL = "MANUAL"
    PERMITTED_ADAPTER = "PERMITTED_ADAPTER"


@dataclass(frozen=True)
class ManualTransfer:
    transfer_id: str
    prompt: str
    instruction: str = "Owner must transfer this prompt to Gemini and return the response manually."


@dataclass(frozen=True)
class GeminiResult:
    text: str
    complete: bool
    untrusted: bool = True


class RetryPolicy:
    def __init__(self, max_retries: int = 1) -> None:
        if not 0 <= max_retries <= 3:
            raise ValueError("max_retries must be between 0 and 3")
        self.max_retries = max_retries


class GeminiAdapter:
    """Prepare manual transfers or call an explicitly injected permitted adapter."""

    def __init__(
        self,
        *,
        mode: TransferMode = TransferMode.MANUAL,
        permitted_transport: Callable[[str], str] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        if mode == TransferMode.PERMITTED_ADAPTER and permitted_transport is None:
            raise ValueError("permitted adapter mode requires an injected transport")
        self.mode = mode
        self._transport = permitted_transport
        self._retry_policy = retry_policy or RetryPolicy()
        self.last_transfer: ManualTransfer | None = None

    def prepare_manual_transfer(self, *, transfer_id: str, prompt: str) -> ManualTransfer:
        if self.mode != TransferMode.MANUAL:
            raise GeminiError("manual transfer is only available in manual mode")
        if not transfer_id.strip() or not prompt.strip() or len(prompt) > 24_000:
            raise GeminiError("transfer ID or prompt is invalid")
        self.last_transfer = ManualTransfer(transfer_id=transfer_id.strip(), prompt=prompt.strip())
        return self.last_transfer

    def accept_manual_response(self, response: str, *, owner_confirmed: bool) -> GeminiResult:
        if self.mode != TransferMode.MANUAL or self.last_transfer is None:
            raise GeminiError("no pending manual transfer")
        if not owner_confirmed:
            raise GeminiError("owner confirmation is required")
        return self._validate_response(response)

    def request(self, prompt: str) -> GeminiResult:
        if self.mode == TransferMode.MANUAL:
            raise GeminiError("manual mode requires prepare_manual_transfer and owner transfer")
        if not prompt.strip() or len(prompt) > 24_000:
            raise GeminiError("prompt is invalid")
        assert self._transport is not None
        last_error: GeminiError | None = None
        for _attempt in range(self._retry_policy.max_retries + 1):
            try:
                return self._validate_response(self._transport(prompt))
            except GeminiIncomplete as exc:
                last_error = exc
            except Exception as exc:
                last_error = GeminiUnavailable("Gemini transport failed")
                break
        raise last_error or GeminiUnavailable("Gemini did not return a complete response")

    @staticmethod
    def _validate_response(response: str) -> GeminiResult:
        if not isinstance(response, str) or not response.strip():
            raise GeminiUnavailable("Gemini response is empty")
        cleaned = response.strip()
        if len(cleaned) < 20 or cleaned.endswith(("…", "...")):
            raise GeminiIncomplete("Gemini response appears incomplete")
        return GeminiResult(text=cleaned, complete=True, untrusted=True)

