"""RSA 加密工具 — 用于 NameSupplement 的敏感字段加密。

服务端使用 numberEncryptPublicKey（RSA 1024-bit PKCS#1 v1.5）加密下列字段：
  - busiAreaName, businessArea, busiAreaData（经营范围）
  - certificateNo, mobile（经办人信息）

公钥来源：GET /icpsp-api/v4/pc/register/tool/sysParams → numberEncryptPublicKey
已在 Tier A 普查数据 sys_params.json 中离线备份。
"""
from __future__ import annotations

import base64
import json
from functools import lru_cache
from pathlib import Path

from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

ROOT = Path(__file__).resolve().parents[2]
SYS_PARAMS_FILE = ROOT / "data" / "dictionaries" / "sys_params.json"


@lru_cache(maxsize=1)
def _load_public_key() -> RSA.RsaKey:
    """从 sys_params.json 加载 numberEncryptPublicKey。"""
    if not SYS_PARAMS_FILE.exists():
        raise FileNotFoundError(f"sys_params.json 不存在: {SYS_PARAMS_FILE}")
    data = json.loads(SYS_PARAMS_FILE.read_text(encoding="utf-8"))
    bd = data
    if "data" in data:
        bd = data["data"]
        if isinstance(bd, dict) and "data" in bd:
            inner = bd["data"]
            bd = inner.get("busiData") if isinstance(inner, dict) else bd
        elif isinstance(bd, dict) and "busiData" in bd:
            bd = bd["busiData"]
    # bd 应该是列表
    pem_b64 = None
    if isinstance(bd, list):
        for item in bd:
            if isinstance(item, dict) and item.get("key") == "numberEncryptPublicKey":
                pem_b64 = item["value"]
                break
    if not pem_b64:
        raise ValueError("numberEncryptPublicKey not found in sys_params.json")
    # 还原 PEM 格式
    pem = f"-----BEGIN PUBLIC KEY-----\n{pem_b64}\n-----END PUBLIC KEY-----"
    return RSA.import_key(pem)


def rsa_encrypt(plaintext: str) -> str:
    """RSA PKCS#1 v1.5 加密，返回 HEX 大写字符串（与前端 JSEncrypt 一致）。"""
    if not plaintext:
        return ""
    key = _load_public_key()
    cipher = PKCS1_v1_5.new(key)
    encrypted = cipher.encrypt(plaintext.encode("utf-8"))
    return encrypted.hex().upper()


def rsa_encrypt_fields(data: dict, fields: list[str]) -> dict:
    """对 dict 中指定字段做 RSA 加密（跳过 None/空）。"""
    for f in fields:
        val = data.get(f)
        if isinstance(val, str) and val:
            data[f] = rsa_encrypt(val)
        elif isinstance(val, (list, dict)):
            data[f] = rsa_encrypt(json.dumps(val, ensure_ascii=False))
    return data
