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
    auth_qr,
    supplement,
    phase2_register,
    matters,
    system as sys_router,
    debug as debug_router,
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
app.include_router(auth_qr.router)
app.include_router(supplement.router)
app.include_router(phase2_register.router)
app.include_router(matters.router)
app.include_router(sys_router.router)
app.include_router(debug_router.router)


@app.get("/healthz")
async def healthz():
    return {"ok": True, "service": "phase1_service"}


@app.get("/")
async def root():
    return {
        "service": "政务平台协议化注册服务（Phase 1 + Phase 2）",
        "version": "0.2.0",
        "endpoints": {
            "POST /api/phase1/register": "Phase 1: 执行 7 步协议链 -> busiId",
            "POST /api/phase1/precheck_name": "名字预检（本地禁用词库 + 可选实网校验）",
            "GET  /api/phase1/auth/status": "Authorization 健康检查",
            "GET  /api/phase1/dict/ent-types": "企业类型字典",
            "GET  /api/phase1/dict/industries/{entType}": "行业码",
            "GET  /api/phase1/dict/organizes/{entType}": "组织形式",
            "GET  /api/phase1/dict/regions": "区划",
            "GET  /api/phase1/dict/name-prefixes/{distCode}/{entType}": "名称前缀",
            "GET  /api/phase1/scope?entType=&busiType=&keyword=": "经营范围 (Tier D)",
            "POST /api/phase1/supplement": "信息补充 + 提交 (Step2+3)",
            "POST /api/phase2/register": "Phase 2: 25 步全链路（stop_after=1~25，默认 14），含幂等缓存 + session 自愈",
            "POST /api/phase2/session/recover": "从 CDP 浏览器手动同步 Authorization + cookies",
            "GET  /api/phase2/cache/stats": "Phase 2 幂等缓存统计",
            "GET  /api/phase2/progress?busi_id=X&name_id=Y": "查询办件当前 establish 位置（currCompUrl + status）",
            "GET  /api/matters/list": "我的办件列表",
            "GET  /api/matters/detail?busi_id=X": "办件详情 + establish 位置",
            "POST /api/auth/token/refresh": "静默续期 Authorization（~2秒，不扫码）",
            "POST /api/auth/token/ensure": "智能获取 token：现有→refresh→qr_needed",
            "POST /api/auth/qr/start?user_type=1": "生成二维码（返回 base64 + sid）",
            "GET  /api/auth/qr/status?sid=X": "轮询扫码状态（扫完自动走 SSO 拿 token）",
            "GET  /api/phase1/scope/search?keyword=X&industry_code=Y": "经营范围实时搜索（平台最新字典）",
            "GET  /api/system/sysparam/snapshot": "本地 sysParam 快照（含 aesKey/RSA 公钥）",
            "GET  /api/system/sysparam/key/{key}": "按 key 查单条 sysParam",
            "POST /api/system/sysparam/refresh": "从平台拉 957 条 sysParam 更新本地快照",
            "GET  /api/debug/mitm/samples?api_pattern=X": "mitm 样本列表（调试辅助）",
            "GET  /api/debug/mitm/latest?api_pattern=X": "最新一条 mitm 样本（完整 req+resp）",
            "GET  /api/debug/mitm/stats": "mitm 抓包统计（总数/方法/top codes/top APIs）",
        },
        "docs": "/docs",
    }
