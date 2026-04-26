"""`/api/system/*` — 平台系统级配置与快照管理。

用途：
- `GET  /api/system/sysparam/snapshot` 读本地 957 条 sysParam 快照（含 aesKey / RSA 公钥）
- `POST /api/system/sysparam/refresh`  调上游 `getAllSysParam` 刷新本地快照
- `GET  /api/system/sysparam/key/{key}` 按 key 查单条

快照文件：`@/UFO/政务平台/dashboard/data/records/sysparam_snapshot.json`
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "system"))

SNAPSHOT_PATH = ROOT / "dashboard" / "data" / "records" / "sysparam_snapshot.json"

router = APIRouter(prefix="/api/system", tags=["system"])


def _load_snapshot() -> Dict[str, Any]:
    """加载本地快照（snapshot 可能是 list[{key,value}] 或 dict）。统一返回 {key: value} dict。"""
    if not SNAPSHOT_PATH.exists():
        return {}
    try:
        raw = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(raw, dict) and "data" not in raw:
        # 已是 {key: value}
        return raw
    if isinstance(raw, list):
        return {item.get("key"): item.get("value") for item in raw if isinstance(item, dict)}
    if isinstance(raw, dict) and "data" in raw:
        data = raw.get("data") or {}
        items = data.get("busiData") or []
        if isinstance(items, list):
            return {item.get("key"): item.get("value") for item in items if isinstance(item, dict)}
    return {}


def _save_snapshot(data: Dict[str, Any]) -> None:
    """保存为 {key: value} dict 格式。"""
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@router.get("/sysparam/snapshot")
async def sysparam_snapshot(
    keys: Optional[str] = Query(default=None, description="逗号分隔的 key 清单，不传则返回全部"),
    mask_keys: bool = Query(default=True, description="对 RSA 公钥等长字段是否折叠"),
) -> Dict[str, Any]:
    """读取本地 sysParam 快照。"""
    snap = _load_snapshot()
    if not snap:
        return {
            "success": False,
            "reason": "snapshot_missing",
            "reason_detail": f"本地快照不存在：{SNAPSHOT_PATH.relative_to(ROOT)}，请先 POST /api/system/sysparam/refresh",
        }

    # 过滤 keys
    if keys:
        want = {k.strip() for k in keys.split(",") if k.strip()}
        data = {k: v for k, v in snap.items() if k in want}
    else:
        data = dict(snap)

    # mask 超长字段（RSA 公钥等）
    if mask_keys:
        for k, v in list(data.items()):
            if isinstance(v, str) and len(v) > 120:
                data[k] = f"{v[:50]}...{v[-40:]} (len={len(v)})"

    mtime = datetime.fromtimestamp(SNAPSHOT_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "success": True,
        "total": len(snap),
        "returned": len(data),
        "snapshot_mtime": mtime,
        "snapshot_path": str(SNAPSHOT_PATH.relative_to(ROOT)),
        "data": data,
    }


@router.get("/sysparam/key/{key}")
async def sysparam_one(key: str) -> Dict[str, Any]:
    """按 key 查单条（不做 mask，便于调用方直接使用）。"""
    snap = _load_snapshot()
    if key not in snap:
        return {"success": False, "reason": "not_found", "key": key}
    return {"success": True, "key": key, "value": snap[key]}


@router.post("/sysparam/refresh")
async def sysparam_refresh() -> Dict[str, Any]:
    """调上游 `/icpsp-api/v4/pc/common/configdata/sysParam/getAllSysParam` 刷新本地快照。

    需要有效 Authorization + session。
    """
    from icpsp_api_client import ICPSPClient  # type: ignore
    client = ICPSPClient()
    try:
        resp = client.get_json("/icpsp-api/v4/pc/common/configdata/sysParam/getAllSysParam")
    except Exception as e:
        return {
            "success": False,
            "reason": "http_error",
            "reason_detail": f"{type(e).__name__}: {str(e)[:200]}",
        }

    code = resp.get("code")
    if code != "00000":
        return {
            "success": False,
            "reason": f"code_{code}",
            "reason_detail": str(resp.get("msg") or "")[:200],
        }

    data = resp.get("data") or {}
    items = data.get("busiData") or []
    if not isinstance(items, list):
        return {
            "success": False,
            "reason": "unexpected_shape",
            "reason_detail": "busiData 不是 list",
        }

    # 转成 {key: value} dict
    kv: Dict[str, Any] = {}
    for it in items:
        if isinstance(it, dict):
            k = it.get("key")
            if k is not None:
                kv[k] = it.get("value")

    prev_snap = _load_snapshot()
    prev_count = len(prev_snap)
    # diff 关键密钥是否变更（方便运维告警）
    important_keys = ("aesKey", "numberEncryptPublicKey", "gsHcpPublicKey", "normAddressAespswd")
    changed_important: List[str] = []
    for k in important_keys:
        if k in prev_snap and k in kv and prev_snap[k] != kv[k]:
            changed_important.append(k)

    _save_snapshot(kv)

    return {
        "success": True,
        "total": len(kv),
        "previous_total": prev_count,
        "snapshot_path": str(SNAPSHOT_PATH.relative_to(ROOT)),
        "important_keys_changed": changed_important,
        "has_aesKey": "aesKey" in kv,
        "has_numberEncryptPublicKey": "numberEncryptPublicKey" in kv,
    }
