#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ICPSP 政务平台前端加密算法的 Python 实现。

来自前端 name-register~*.js:
```
encrypt(e):           // RSA 加密（身份证、手机号等敏感数字）
    t = getSysConfigByCode("numberEncryptPublicKey")
    return new JSEncrypt.setPublicKey(t).encrypt(e)  // PKCS1v15, Base64

aesEncrypt(e):        // AES-128-CBC 加密（经营范围等大块业务数据）
    t = getSysConfigByCode("aesKey")   // 16 字符 UTF-8
    key = CryptoJS.enc.Utf8.parse(t)
    iv  = CryptoJS.enc.Utf8.parse(t)   // iv == key
    return AES.encrypt(e, key, {mode:CBC, iv, padding:Pkcs7})
           .ciphertext.toString().toUpperCase()   // hex 大写
```

密钥来自 `/icpsp-api/v4/pc/common/configdata/sysParam/getAllSysParam`
(2026-04-23 抓取):
  · aesKey = "topneticpsp12345"
  · numberEncryptPublicKey = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCCtpet..."
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, serialization


ROOT = Path("G:/UFO/政务平台")
SYSPARAM_SNAPSHOT = ROOT / "dashboard" / "data" / "records" / "sysparam_snapshot.json"

# 缓存
_sysparam_cache: Optional[dict] = None


def load_sysparam() -> dict:
    """加载 sysparam snapshot。若不存在，调用 _phase2_extract_sysparam_keys.py 生成。"""
    global _sysparam_cache
    if _sysparam_cache is not None:
        return _sysparam_cache
    if not SYSPARAM_SNAPSHOT.exists():
        raise FileNotFoundError(
            f"sysparam snapshot not found: {SYSPARAM_SNAPSHOT}\n"
            "请先跑: .\\.venv-portal\\Scripts\\python.exe system\\_phase2_extract_sysparam_keys.py"
        )
    _sysparam_cache = json.loads(SYSPARAM_SNAPSHOT.read_text(encoding="utf-8"))
    return _sysparam_cache


def get_aes_key() -> str:
    return load_sysparam()["aesKey"]


def get_rsa_public_key_pem() -> str:
    """返回完整 PEM 格式的公钥。"""
    raw = load_sysparam()["numberEncryptPublicKey"]
    # 如果已经是完整 PEM（包含 -----BEGIN---），直接返回
    if "-----BEGIN" in raw:
        return raw
    # 否则用 -----BEGIN/END PUBLIC KEY----- 包起来（每 64 字符换行）
    body = raw.strip().replace("\n", "").replace("\r", "")
    lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    return "-----BEGIN PUBLIC KEY-----\n" + "\n".join(lines) + "\n-----END PUBLIC KEY-----"


def aes_encrypt(plaintext: str, key: Optional[str] = None) -> str:
    """AES-128-CBC，key=iv=UTF8(aesKey)，PKCS7，返回大写 HEX。对齐前端 aesEncrypt。"""
    if not plaintext:
        return plaintext
    k = (key or get_aes_key()).encode("utf-8")
    if len(k) != 16:
        # AES-128 要求 16 字节；若不是 16，截断/补 0
        k = (k + b"\0" * 16)[:16]
    iv = k  # iv == key
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(k), modes.CBC(iv))
    ct = cipher.encryptor().update(padded) + cipher.encryptor().finalize()
    return ct.hex().upper()


def aes_decrypt(hex_ciphertext: str, key: Optional[str] = None) -> str:
    """AES-128-CBC 解密。调试用（验证加密是否正确）。"""
    k = (key or get_aes_key()).encode("utf-8")
    if len(k) != 16:
        k = (k + b"\0" * 16)[:16]
    iv = k
    ct = bytes.fromhex(hex_ciphertext)
    dec = Cipher(algorithms.AES(k), modes.CBC(iv)).decryptor()
    padded = dec.update(ct) + dec.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    plain = unpadder.update(padded) + unpadder.finalize()
    return plain.decode("utf-8")


def rsa_encrypt(plaintext: str, pem: Optional[str] = None) -> str:
    """RSA-PKCS1v15 加密，返回 Base64。对齐前端 JSEncrypt.encrypt。

    注意：PKCS1v15 每次加密结果不同（padding 含随机字节），这是正常的。"""
    if not plaintext:
        return plaintext
    pem_str = pem or get_rsa_public_key_pem()
    pk = serialization.load_pem_public_key(pem_str.encode("utf-8"))
    ct = pk.encrypt(plaintext.encode("utf-8"), asym_padding.PKCS1v15())
    return base64.b64encode(ct).decode("ascii")


# ─── 自测 ───
if __name__ == "__main__":
    print("=== ICPSP 加密模块自测 ===\n")
    print(f"aesKey = {get_aes_key()!r}")
    print(f"RSA public key PEM (前 80 字):")
    print(f"  {get_rsa_public_key_pem()[:200]}...\n")

    # AES 测试
    p = "450921198812051251"
    c = aes_encrypt(p)
    d = aes_decrypt(c)
    ok = (d == p)
    print(f"AES 加密测试:")
    print(f"  明文: {p}")
    print(f"  密文: {c}")
    print(f"  回解: {d}")
    print(f"  ✓ round-trip OK" if ok else f"  ✗ FAILED")
    print()

    # RSA 测试
    p2 = "450921198812051251"
    c2 = rsa_encrypt(p2)
    print(f"RSA 加密测试:")
    print(f"  明文: {p2}")
    print(f"  密文 (Base64, {len(c2)} chars): {c2[:80]}...{c2[-40:]}")
    print(f"  ✓ 长度符合 RSA-1024 (128 字节 → Base64 172 字符)" if len(c2) == 172 else f"  ✗ 长度异常")

    # 对比样本
    print(f"\n=== 对比 mitm 样本 ===")
    sample = "Nzwt4k47DulOHusNfdeHu3UBVp3KTHZJUe8aWOFFSBfFBzC10X7TvDynQNw9cgUADkLbR9AXg//hB0+TmHAN0Rr8+q9dsHjnY/b56Fax5xVWVhPuv9ag9h+NV+awoiORhBlFciSLGMbHX8fwAk2RuLwU2B9XvQyzC0XAuxToT3w="
    print(f"  样本密文长度: {len(sample)} chars")
    print(f"  我们加密长度: {len(c2)} chars")
    print(f"  结构匹配（长度/Base64） : {'✓' if len(sample) == len(c2) else '✗'}")
