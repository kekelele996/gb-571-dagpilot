"""路由聚合：统一 /api 前缀（Nginx 反代时剥掉 /api）。"""
from fastapi import APIRouter

from src.routes.audit import router as audit_router
from src.routes.auth import router as auth_router
from src.routes.exports import router as exports_router
from src.routes.health import router as health_router
from src.routes.jobs import router as jobs_router
from src.routes.simulations import router as simulations_router
from src.routes.sla import router as sla_router
from src.routes.watch import router as watch_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(jobs_router)
api_router.include_router(simulations_router)
api_router.include_router(sla_router)
api_router.include_router(watch_router)
api_router.include_router(exports_router)
api_router.include_router(audit_router)
