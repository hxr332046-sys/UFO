#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
设立登记迭代入口：默认使用「全部服务」截图同款 URL（guide/base 回跳），
跑通 portal → 设立登记 → 专区/名称子应用 → 尽量 guide/base，并写入带 AC-xx 验收字段的 JSON。

等价命令：
  python packet_chain_portal_from_start.py --entry guide --iter-latest
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 允许从仓库任意 cwd 执行：python G:\...\system\establish_iterate_dev.py
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from packet_chain_portal_from_start import OUT_ITER_LATEST, run


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--entry",
        choices=("guide", "namenotice"),
        default="guide",
        help="guide=全部服务页（fromPage=/guide/base）；namenotice=declaration-instructions 回跳",
    )
    ap.add_argument("-o", "--output", type=Path, default=None, help="自定义 JSON 路径")
    args = ap.parse_args()
    run(entry=args.entry, out_path=args.output, also_write_iter_latest=True)
    print("迭代对照文件:", OUT_ITER_LATEST)


if __name__ == "__main__":
    main()
