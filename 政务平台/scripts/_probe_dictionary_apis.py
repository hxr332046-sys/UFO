"""主动探测可能的 dictionary 接口。

策略：尝试多种常见接口路径 + 多种参数组合，凡是返回 code=00000 + busiData 是数组的，
都视为字典接口，喂给 OptionsScout 沉淀。
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient
from governance import OptionsScout, OptionDict


# 候选接口路径（从猜测 + 政务平台常见命名规律）
CANDIDATE_PATHS = [
    "/icpsp-api/v4/pc/sys/dictionary/list",
    "/icpsp-api/v4/pc/sys/dict/list",
    "/icpsp-api/v4/pc/sys/dict/getByType",
    "/icpsp-api/v4/pc/sys/dict/getDictByType",
    "/icpsp-api/v4/pc/dict/getByType",
    "/icpsp-api/v4/pc/dict/list",
    "/icpsp-api/v4/pc/manager/sys/dict/list",
    "/icpsp-api/v4/pc/manager/dictionary/list",
    "/icpsp-api/v4/pc/manager/usermanager/getDict",
    "/icpsp-api/v4/pc/common/dictionary",
    "/icpsp-api/v4/pc/common/getDict",
    "/icpsp-api/v4/pc/register/dict/list",
    "/icpsp-api/v4/pc/register/common/getDict",
    "/icpsp-api/v4/pc/register/establish/getDict",
]

# 候选 type 参数（猜测可能的字典类型）
CANDIDATE_TYPES = [
    "politicalStatus",      # 政治面貌
    "politicsVisage",
    "edu",                  # 学历
    "eduDegree",
    "education",
    "cerType",              # 证件类型
    "certType",
    "sex",                  # 性别
    "country",              # 国籍
    "yesOrNo",              # 是否
    "investWay",            # 出资方式
    "investType",
    "subInvestType",
    "propertyUseMode",      # 房产使用方式
    "houseUseMode",
    "houseToBus",           # 住改商
    "industry",             # 行业
    "entType",              # 企业类型
]


def main():
    client = ICPSPClient()
    od = OptionDict.load()
    scout = OptionsScout(od, log=True)
    client.register_response_observer(scout.as_observer())

    # 验证登录
    try:
        ui = client.get_json("/icpsp-api/v4/pc/manager/usermanager/getUserInfo", params={})
        if ui.get("code") != "00000":
            print(f"❌ 未登录或 token 失效: {ui}")
            return 1
        print(f"✅ 登录有效: {(ui.get('data') or {}).get('busiData', {}).get('realName')}")
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return 1

    print(f"\n开始探测 {len(CANDIDATE_PATHS)} × {len(CANDIDATE_TYPES)} = "
          f"{len(CANDIDATE_PATHS) * len(CANDIDATE_TYPES)} 个组合...")

    success_paths = []
    findings = {}

    for path in CANDIDATE_PATHS:
        # 先无参数试一次（看接口存不存在）
        try:
            r = client.post_json(path, {})
            code = r.get("code", "")
            if code in ("00000", "D0001", "0"):  # 0 也可能是成功
                bd = (r.get("data") or {}).get("busiData")
                if bd:
                    success_paths.append(path)
                    print(f"  ✅ {path} 无参 → code={code}, busiData type={type(bd).__name__}")
        except Exception:
            continue

    print(f"\n无参可达接口: {len(success_paths)}")
    if not success_paths:
        # 测试所有 type 在 sys/dict/list（最常见命名）
        print("\n尝试遍历 type 参数（在所有 path 上）...")
        for path in CANDIDATE_PATHS:
            for t in CANDIDATE_TYPES:
                for body_form in [
                    {"type": t},
                    {"dictType": t},
                    {"code": t},
                    {"key": t},
                ]:
                    try:
                        r = client.post_json(path, body_form)
                        code = r.get("code", "")
                        if code == "00000":
                            bd = (r.get("data") or {}).get("busiData")
                            if bd and (isinstance(bd, list) and bd or
                                       isinstance(bd, dict) and any(isinstance(v, list) and v for v in bd.values())):
                                key = f"{path}:{t}:{json.dumps(body_form)}"
                                findings[key] = (code, str(bd)[:200])
                                print(f"  ✅ {path}  type={t}  body={body_form}  → 返回数据")
                    except Exception:
                        continue

    # 汇总
    print("\n=== 探测汇总 ===")
    if success_paths:
        for p in success_paths:
            print(f"  ✓ {p}")
    if findings:
        for k, v in findings.items():
            print(f"  ★ {k}")
            print(f"      {v[1][:200]}")

    if not success_paths and not findings:
        print("  ❌ 未发现独立 dictionary 接口")
        print("  → 服务端可能没有专门字典接口，枚举值随业务接口返回或硬编码在前端")

    # 持久化 scout 的发现
    scout.persist()
    return 0


if __name__ == "__main__":
    sys.exit(main())
