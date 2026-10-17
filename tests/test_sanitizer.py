import pytest
from src.telemetry.sanitizer import REDACTED_VALUE, TelemetrySanitizer


def test_sanitizer_masks_direct_sensitive_keys() -> None:
    sanitizer = TelemetrySanitizer()
    payload = {
        "username": "jdoe",
        "password": "p@ssword123",
        "cpf": "123.456.789-00",
        "auth": "Bearer xyz789",
    }
    sanitized = sanitizer.sanitize(payload)

    assert sanitized["username"] == "jdoe"
    assert sanitized["password"] == REDACTED_VALUE
    assert sanitized["cpf"] == REDACTED_VALUE
    assert sanitized["auth"] == REDACTED_VALUE


def test_sanitizer_case_insensitive_keys() -> None:
    sanitizer = TelemetrySanitizer()
    payload = {
        "PASSWORD": "secret",
        "Secret": "shh",
        "API_KEY": "token123",
        "safe_key": "safe_val",
    }
    sanitized = sanitizer.sanitize(payload)

    assert sanitized["PASSWORD"] == REDACTED_VALUE
    assert sanitized["Secret"] == REDACTED_VALUE
    assert sanitized["API_KEY"] == REDACTED_VALUE
    assert sanitized["safe_key"] == "safe_val"


def test_sanitizer_masks_nested_dictionaries() -> None:
    sanitizer = TelemetrySanitizer()
    payload = {
        "user": {
            "id": 42,
            "credentials": {
                "password": "nested_pass",
                "token": "abc_token",
            },
            "preferences": {
                "theme": "dark"
            }
        }
    }
    sanitized = sanitizer.sanitize(payload)

    assert sanitized["user"]["id"] == 42
    assert sanitized["user"]["preferences"]["theme"] == "dark"
    assert sanitized["user"]["credentials"]["password"] == REDACTED_VALUE
    assert sanitized["user"]["credentials"]["token"] == REDACTED_VALUE


def test_sanitizer_masks_within_collections() -> None:
    sanitizer = TelemetrySanitizer()
    payload = {
        "users": [
            {"name": "Alice", "cpf": "111.222.333-44"},
            {"name": "Bob", "cpf": "555.666.777-88"},
        ],
        "tags": ("prod", "auth"),
        "ids": {1, 2, 3},
    }
    sanitized = sanitizer.sanitize(payload)

    assert sanitized["users"][0]["cpf"] == REDACTED_VALUE
    assert sanitized["users"][1]["cpf"] == REDACTED_VALUE
    assert sanitized["users"][0]["name"] == "Alice"
    assert sanitized["tags"] == ("prod", "auth")
    assert sanitized["ids"] == {1, 2, 3}


def test_sanitizer_inline_cpf_regex_in_strings() -> None:
    sanitizer = TelemetrySanitizer()
    payload = {
        "message": "Usuário com CPF 123.456.789-00 solicitou alteração de dados",
        "raw_cpf": "98765432100",
    }
    sanitized = sanitizer.sanitize(payload)

    assert REDACTED_VALUE in sanitized["message"]
    assert "123.456.789-00" not in sanitized["message"]


def test_custom_sanitizer_keys_and_patterns_disabled() -> None:
    sanitizer = TelemetrySanitizer(
        sensitive_keys=["custom_field"],
        mask_pattern="***MASKED***",
        sanitize_patterns=False,
    )
    payload = {
        "custom_field": "secret_value",
        "cpf": "123.456.789-00",
    }
    sanitized = sanitizer.sanitize(payload)

    assert sanitized["custom_field"] == "***MASKED***"
    # Como CPF não está em custom_field e sanitize_patterns=False, mantém original
    assert sanitized["cpf"] == "123.456.789-00"
