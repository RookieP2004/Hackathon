from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """
    Every service exposes this identical contract (ARCHITECTURE.md §8.2) so the
    observability stack and Docker Compose healthchecks can treat all 14 services
    uniformly. Real dependency checks (DB connectivity, etc.) are added per-service
    as each service's actual migrations/integrations land — this is the structural
    baseline every service starts from.
    """
    return {"status": "ok"}
