"""
Every service ships the same literal placeholder as its jwt_secret/database
password default, so a real deployment stays runnable without extra config
in local dev -- but that also means a forgotten env var in a shared
environment silently produces a system-wide auth bypass (anyone who reads
the public source knows the "secret" every service actually verifies tokens
against). This is the one check every service's startup calls to refuse to
boot in that situation, rather than degrading silently.
"""

from __future__ import annotations

PLACEHOLDER_SECRETS = {
    "changeme_generate_a_real_secret_before_any_shared_deployment",
    "changeme_local_only",
}


def assert_not_placeholder_secret(value: str, *, aegis_env: str, name: str) -> None:
    if aegis_env != "local" and value in PLACEHOLDER_SECRETS:
        raise RuntimeError(
            f"{name} is still the shipped placeholder value outside a local environment "
            f"(aegis_env={aegis_env!r}) -- refusing to start. Set a real, unique {name} via environment variable."
        )
