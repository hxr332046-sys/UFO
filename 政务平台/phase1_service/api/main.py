"""FastAPI 入口。

启动：
  # 开发模式
  uvicorn phase1_service.api.main:app --host 0.0.0.0 --port 8800 --reload

  # 生产模式
  uvicorn phase1_service.api.main:app --host 0.0.0.0 --port 8800
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[2]
# 让 phase1_service 与 system 都可被 import
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "system"))

from phase1_service.api.routers import (  # noqa: E402
    registration,
    dictionaries,
    business_scope,
    precheck,
    auth,
    supplement,
)

app = FastAPI(
    title="第一阶段名称登记服务",
    description=(
        "基于 phase1_protocol_driver 封装的内部 API。\n"
        "- POST /api/phase1/register 执行 7 步协议链拿 busiId\n"
        "- GET /api/phase1/dict/* 本地字典（Tier A-C 普查产物）\n"
        "- GET /api/phase1/scope 经营范围（Tier D 普查产物）"
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境请收紧
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(registration.router)
app.include_router(dictionaries.router)
app.include_router(business_scope.router)
app.include_router(precheck.router)
app.include_router(auth.router)
app.include_router(supplement.router)


@app.get("/healthz")
async def healthz():
    return {"ok": True, "service": "phase1_service"}


@app.get("/")
async def root():
    return {
        "service": "第一阶段名称登记服务",
        "version": "0.1.0",
        "endpoints": {
            "POST /api/phase1/register": "执行 7 步协议链 -> busiId",
            "POST /api/phase1/precheck_name": "名字预检（本地禁用词库 + 可选实网校验）",
            "GET  /api/phase1/auth/status": "Authorization 健康检查",
            "GET  /api/phase1/dict/ent-types": "企业类型字典",
            "GET  /api/phase1/dict/industries/{entType}": "行业码",
            "GET  /api/phase1/dict/organizes/{entType}": "组织形式",
            "GET  /api/phase1/dict/regions": "区划",
            "GET  /api/phase1/dict/name-prefixes/{distCode}/{entType}": "名称前缀",
            "GET  /api/phase1/scope?entType=&busiType=&keyword=": "经营范围 (Tier D)",
            "POST /api/phase1/supplement": "信息补充 + 提交 (Step2+3)",
        },
        "docs": "/docs",
    }
