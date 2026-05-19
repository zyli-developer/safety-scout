"""Healthz —— 浅探测，不验下游可达性（T6 视需要再加深度检查）。"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
