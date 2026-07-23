"""
Shared service-to-service token minting. Several services need to call
another authenticated service on behalf of a real actor (never a fabricated
principal): agentic-orchestrator's ServiceClients/KnowledgeAgent and
predictive-risk-engine's fusion pipeline all independently re-implemented
the identical "look up a real seeded user with this role, mint a short-lived
access token, cache it" logic before this was extracted. One implementation
here, reused everywhere, so a future change to the token shape only needs
to happen once.
"""

from __future__ import annotations

import time

import asyncpg
from jose import jwt


class ServiceActorTokenMinter:
    """Mints a real, short-lived access token as a real seeded actor (by
    role name), caching it in memory until shortly before it expires."""

    def __init__(self, *, postgres_dsn: str, jwt_secret: str, jwt_algorithm: str, actor_role_name: str = "safety_officer") -> None:
        self._postgres_dsn = postgres_dsn
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm
        self._actor_role_name = actor_role_name
        self._cached_token: str | None = None
        self._token_expires_at: float = 0.0

    async def get_token(self) -> str:
        now = time.time()
        if self._cached_token and now < self._token_expires_at - 30:
            return self._cached_token

        conn = await asyncpg.connect(self._postgres_dsn)
        try:
            row = await conn.fetchrow(
                "SELECT u.id, u.default_role_id FROM users u JOIN roles r ON r.id = u.default_role_id WHERE r.name = $1 LIMIT 1",
                self._actor_role_name,
            )
        finally:
            await conn.close()

        expires_at = now + 600
        token = jwt.encode(
            {"sub": str(row["id"]), "role_id": row["default_role_id"], "type": "access", "exp": int(expires_at)},
            self._jwt_secret, algorithm=self._jwt_algorithm,
        )
        self._cached_token, self._token_expires_at = token, expires_at
        return token

    async def auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {await self.get_token()}"}
