from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Same contract every service exposes (ARCHITECTURE.md §8.2)."""
    return {"status": "ok"}
