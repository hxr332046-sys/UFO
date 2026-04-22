"""普查通用工具：限流、保存、校验、从 ICPSP 客户端发请求。"""
from __future__ import annotations

import hashlib
import json
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "system"))

from icpsp_api_client import ICPSPClient  # noqa: E402


@dataclass
class PaceConfig:
    min_interval_ms: int = 2000
    max_interval_ms: int = 3500
    d0029_cooldown_sec: int = 600
    d0029_retry_threshold: int = 2


@dataclass
class CensusState:
    """普查状态：记录每个请求的完成情况，支持断点续跑。"""
    completed: Dict[str, Dict[str, Any]] = field(default_factory=dict)   # key -> {status, saved_path, ts}
    failed: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    d0029_count: int = 0
    total_requests: int = 0

    def key(self, job_id: str, params: Dict[str, Any]) -> str:
        sig = json.dumps(params, ensure_ascii=False, sort_keys=True)
        h = hashlib.md5(sig.encode("utf-8")).hexdigest()[:12]
        return f"{job_id}::{h}"

    @classmethod
    def load(cls, p: Path) -> "CensusState":
        if not p.exists():
            return cls()
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            return cls(
                completed=d.get("completed", {}),
                failed=d.get("failed", {}),
                d0029_count=d.get("d0029_count", 0),
                total_requests=d.get("total_requests", 0),
            )
        except Exception:
            return cls()

    def save(self, p: Path) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps({
                "completed": self.completed,
                "failed": self.failed,
                "d0029_count": self.d0029_count,
                "total_requests": self.total_requests,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def pace_sleep(pace: PaceConfig) -> None:
    """礼貌等待：min-max ms 均匀随机。"""
    dur = random.randint(pace.min_interval_ms, pace.max_interval_ms) / 1000.0
    time.sleep(dur)


def do_get(client: ICPSPClient, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """统一 GET（ICPSPClient 内部会自动追加 t= 时间戳）。"""
    try:
        resp = client.get_json(path, params=dict(params or {}))
    except Exception as e:
        return {"_ok": False, "_err": repr(e)}
    return resp


def check_rate_limit(resp: Dict[str, Any]) -> bool:
    """True 表示触发 D0029 或可能风控。"""
    if not isinstance(resp, dict):
        return False
    code = str(resp.get("code") or "")
    msg = str(resp.get("msg") or "")
    if code == "D0029" or "频繁" in msg or "操作频繁" in msg:
        return True
    return False


def save_payload(out_path: Path, payload: Dict[str, Any], meta: Dict[str, Any]) -> None:
    """把接口响应落盘，带元数据（请求路径/参数/响应时间等）。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper = {
        "schema": "phase1_service.census.payload.v1",
        "meta": meta,
        "data": payload,
    }
    out_path.write_text(json.dumps(wrapper, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_busi_data(resp: Dict[str, Any]) -> Any:
    """按 ICPSP 响应约定取 data.busiData。"""
    if not isinstance(resp, dict):
        return None
    d = resp.get("data")
    if isinstance(d, dict):
        return d.get("busiData")
    return None
