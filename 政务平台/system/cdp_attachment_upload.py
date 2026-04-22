#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CDP DOM.setFileInputFiles：按表单项文案匹配身份证正/反面，其余槽位用模拟文件（不弹系统对话框）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 与 packet_chain 一致：须先 configure_human_pacing；未配置时 sleep_human 仍有默认 ≥1s 下限
from human_pacing import sleep_human

# 探测每个 file input 附近的表单项标签（Element UI 常见结构）
PROBE_FILE_CONTEXT_JS = r"""(function(){
  var inputs=[...document.querySelectorAll('input[type=file]')];
  function labelFor(inp){
    var lab='';
    var cur=inp;
    for(var d=0;d<18;d++){
      cur=cur.parentElement;
      if(!cur) break;
      var fw=cur.closest&&cur.closest('.el-form-item');
      if(fw){
        var l2=fw.querySelector('.el-form-item__label');
        if(l2){
          lab=(l2.textContent||'').replace(/\s+/g,' ').trim();
          if(lab) break;
        }
      }
      var l=cur.querySelector&&cur.querySelector(':scope > .el-form-item__label');
      if(l){
        lab=(l.textContent||'').replace(/\s+/g,' ').trim();
        if(lab) break;
      }
    }
    return lab.slice(0,120);
  }
  return inputs.map(function(inp, idx){
    var r=inp.getBoundingClientRect();
    var vis=r.width>0&&r.height>0&&inp.offsetParent!==null;
    return {
      idx: idx,
      label: labelFor(inp),
      accept: (inp.getAttribute('accept')||'').slice(0,120),
      multiple: !!inp.multiple,
      approxVisible: vis
    };
  });
})()"""


def pick_path_for_slot(
    label: str,
    accept: str,
    *,
    id_front: Path,
    id_back: Path,
    mock_image: Path,
    mock_pdf: Path,
    lease_contract: Optional[Path] = None,
) -> Tuple[Path, str]:
    """返回 (绝对路径, 匹配原因)。"""
    t = label or ""
    if lease_contract is not None and lease_contract.is_file():
        if any(k in t for k in ("租赁", "租约", "合同", "协议", "场地", "住所证明", "产权")):
            return lease_contract, "lease_contract_label"
    if any(k in t for k in ("人像", "正面", "头像面")):
        return id_front, "id_front_label"
    if any(k in t for k in ("国徽", "反面", "背面")):
        return id_back, "id_back_label"
    acc = (accept or "").lower()
    if ".pdf" in acc or "application/pdf" in acc:
        return mock_pdf, "accept_pdf"
    return mock_image, "mock_generic"


def ensure_rehearsal_mock_dir(root: Path) -> Dict[str, Path]:
    """生成最小可上传的模拟文件（合约/租约等占位）。"""
    d = root / "packet_lab" / "out" / "rehearsal_mock"
    d.mkdir(parents=True, exist_ok=True)
    pdf = d / "mock_contract.pdf"
    if not pdf.is_file():
        pdf.write_bytes(
            b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 200 200]/Parent 2 0 R>>endobj\n"
            b"trailer<</Size 4/Root 1 0 R>>\n%%EOF\n"
        )
    jpg = d / "mock_placeholder.jpg"
    if not jpg.is_file() or jpg.stat().st_size < 20:
        # 最小合法 JPEG（约 600B）
        import base64

        jpg.write_bytes(
            base64.b64decode(
                "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsL"
                "DBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/"
                "2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
                "MjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDAREAAhEBAxEB/8QAFQAB"
                "AQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oA"
                "DAMBAAIQAxAAAAG/AP/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEA"
                "AT8h/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPx//xAAUEAEA"
                "AAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/EH//2Q=="
            )
        )
    return {"mock_pdf": pdf, "mock_image": jpg}


def load_assets_cfg(path: Path, root: Path) -> Dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    mocks = ensure_rehearsal_mock_dir(root)
    front = Path(raw["id_front"])
    back = Path(raw["id_back"])
    lease: Optional[Path] = None
    if raw.get("lease_contract"):
        lease = Path(str(raw["lease_contract"]))
    return {
        "id_front": front,
        "id_back": back,
        "lease_contract": lease,
        "mock_pdf": mocks["mock_pdf"],
        "mock_image": mocks["mock_image"],
        "raw": raw,
    }


def dom_set_files_on_inputs(cdp: Any, paths: List[Optional[str]]) -> List[Dict[str, Any]]:
    """cdp 须含 .call(method, params)。paths 与 DOM querySelectorAll 顺序对齐。"""
    out: List[Dict[str, Any]] = []
    cdp.call("DOM.enable", {})
    doc_msg = cdp.call("DOM.getDocument", {"depth": 0})
    if doc_msg.get("error"):
        return [{"error": "getDocument", "detail": doc_msg}]
    root_id = (doc_msg.get("result") or {}).get("root", {}).get("nodeId")
    if not root_id:
        return [{"error": "no_root_node"}]
    qs = cdp.call("DOM.querySelectorAll", {"nodeId": root_id, "selector": "input[type='file']"})
    if qs.get("error"):
        return [{"error": "querySelectorAll", "detail": qs}]
    node_ids = (qs.get("result") or {}).get("nodeIds") or []
    for i, p in enumerate(paths):
        if i >= len(node_ids):
            out.append({"idx": i, "skipped": True, "reason": "no_nodeId"})
            continue
        if not p:
            out.append({"idx": i, "skipped": True, "reason": "no_path"})
            continue
        fp = str(Path(p).resolve())
        msg = cdp.call("DOM.setFileInputFiles", {"nodeId": node_ids[i], "files": [fp]})
        ok = not msg.get("error")
        out.append({"idx": i, "path": fp, "ok": ok, "cdp": msg.get("error") or msg.get("result")})
        # 每槽上传后与下一槽间隔 ≥1s（框架固化规则）
        sleep_human(1.0)
    return out


def try_upload_for_current_page(r: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    """
    r: _ResilientCDP（用 .raw 访问底层 CDP）。
    assets: load_assets_cfg 返回值。
    """
    probe = r.ev(PROBE_FILE_CONTEXT_JS, tag="file_probe")
    if not isinstance(probe, list) or not probe:
        return {"skipped": True, "reason": "no_file_inputs", "probe": probe}

    paths: List[Optional[str]] = []
    plan: List[Dict[str, Any]] = []
    for row in probe:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "")
        accept = str(row.get("accept") or "")
        pth, why = pick_path_for_slot(
            label,
            accept,
            id_front=assets["id_front"],
            id_back=assets["id_back"],
            mock_image=assets["mock_image"],
            mock_pdf=assets["mock_pdf"],
            lease_contract=assets.get("lease_contract"),
        )
        if not pth.is_file():
            plan.append({"idx": row.get("idx"), "label": label, "error": "missing_file", "path": str(pth)})
            paths.append(None)
        else:
            plan.append({"idx": row.get("idx"), "label": label, "match": why, "path": str(pth)})
            paths.append(str(pth))

    results = dom_set_files_on_inputs(r.raw, paths)
    return {"probe": probe, "plan": plan, "dom_results": results}
