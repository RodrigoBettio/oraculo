import re
from typing import Any, Collection

DEFAULT_SENSITIVE_KEYS: frozenset[str] = frozenset({
    "password",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_token",
    "auth",
    "authorization",
    "cpf",
    "cnpj",
    "ssn",
    "credit_card",
    "card_number",
    "cvv",
    "cvc",
})

REDACTED_VALUE: str = "[REDACTED]"
CPF_REGEX: re.Pattern[str] = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")


class TelemetrySanitizer:
    def __init__(
        self,
        sensitive_keys: Collection[str] | None = None,
        mask_pattern: str = REDACTED_VALUE,
        sanitize_patterns: bool = True,
    ) -> None:
        self._sensitive_keys: set[str] = {
            k.lower() for k in (sensitive_keys if sensitive_keys is not None else DEFAULT_SENSITIVE_KEYS)
        }
        self._mask: str = mask_pattern
        self._sanitize_patterns: bool = sanitize_patterns

    def sanitize(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: self._sanitize_entry(str(k), v) for k, v in data.items()}
        elif isinstance(data, (list, tuple, set)):
            sanitized_items = [self.sanitize(item) for item in data]
            return type(data)(sanitized_items)
        elif isinstance(data, str) and self._sanitize_patterns:
            return self._sanitize_string_value(data)
        return data

    def _sanitize_entry(self, key: str, value: Any) -> Any:
        if key.strip().lower() in self._sensitive_keys:
            return self._mask
        return self.sanitize(value)

    def _sanitize_string_value(self, value: str) -> str:
        if CPF_REGEX.search(value):
            return CPF_REGEX.sub(self._mask, value)
        return value
