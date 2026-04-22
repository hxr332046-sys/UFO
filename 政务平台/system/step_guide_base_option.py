#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from human_pacing import configure_human_pacing, sleep_human  # noqa: E402
from packet_chain_portal_from_start import S08_STATE_PROBE_JS  # noqa: E402
from cdp_helper import create_helper  # noqa: E402


PROBE_OR_CLICK_JS = r"""
(function(groupText, targetText, fuzzy){
  function norm(s){ return String(s || '').replace(/\s+/g, ' ').trim(); }
  function vis(e){
    if(!e) return false;
    var s = getComputedStyle(e);
    return s.display !== 'none' && s.visibility !== 'hidden' && (e.offsetWidth > 0 || e.offsetHeight > 0);
  }
  function collectLabels(root){
    var base = root || document;
    var labels = Array.prototype.slice.call(base.querySelectorAll('label.tni-radio.text-center')).filter(vis);
    var out = [];
    for(var i=0;i<labels.length;i++){
      var lb = labels[i];
      var txt = norm(lb.innerText || lb.textContent || '');
      var inp = lb.querySelector('input');
      out.push({
        index: i,
        text: txt,
        cls: (lb.className || '') + '',
        checked: ((lb.className || '') + '').indexOf('is-checked') >= 0,
        value: inp ? (inp.value || '') : ''
      });
    }
    return {labels: labels, rows: out};
  }
  function findGroupRoot(text){
    if(!text) return null;
    var nodes = Array.prototype.slice.call(document.querySelectorAll('h1,h2,h3,.title,div,span,label')).filter(vis);
    for(var i=0;i<nodes.length;i++){
      var t = norm(nodes[i].innerText || nodes[i].textContent || '');
      if(!t || t.length > 40) continue;
      if(t.indexOf(text) < 0) continue;
      var cur = nodes[i];
      for(var step=0; step<6 && cur; step++){
        if(cur.querySelector){
          var g = cur.querySelector('.tni-radio-group');
          if(g) return g;
        }
        cur = cur.nextElementSibling;
        if(cur && cur.matches && cur.matches('.tni-radio-group')) return cur;
      }
    }
    return null;
  }
  var root = findGroupRoot(groupText);
  var pack = collectLabels(root);
  if(!targetText){
    return {ok:true, mode:'probe', groupText:groupText || '', foundGroup:!!root, options:pack.rows};
  }
  var hit = null;
  for(var j=0;j<pack.rows.length;j++){
    var row = pack.rows[j];
    if(row.text === targetText){ hit = {row: row, el: pack.labels[j]}; break; }
    if(!hit && fuzzy && row.text.indexOf(targetText) >= 0){ hit = {row: row, el: pack.labels[j]}; }
  }
  if(!hit){
    return {ok:false, mode:'click', groupText:groupText || '', targetText:targetText, foundGroup:!!root, options:pack.rows};
  }
  try{ hit.el.click(); }catch(e){}
  try{ hit.el.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window})); }catch(e){}
  try{
    var label = hit.el.querySelector('.tni-radio__label');
    if(label){ label.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window})); }
  }catch(e){}
  try{
    var inp = hit.el.querySelector('input');
    if(inp){ inp.click(); inp.checked = true; }
  }catch(e){}
  var after = collectLabels(root).rows;
  return {
    ok:true,
    mode:'click',
    groupText:groupText || '',
    targetText:targetText,
    foundGroup:!!root,
    clicked: hit.row,
    after: after
  };
})(%GROUP_TEXT%, %TARGET_TEXT%, %FUZZY%)
"""


def render_js(group_text: str | None, target_text: str | None, fuzzy: bool) -> str:
    js = PROBE_OR_CLICK_JS.replace("%GROUP_TEXT%", json.dumps(group_text, ensure_ascii=False))
    js = js.replace("%TARGET_TEXT%", json.dumps(target_text, ensure_ascii=False))
    js = js.replace("%FUZZY%", "true" if fuzzy else "false")
    return js


def main() -> int:
    ap = argparse.ArgumentParser(description="guide/base 单步探测/点击单选项")
    ap.add_argument("--group", default="", help="分组标题关键字，如 是否已申请名称 / 市场主体类型")
    ap.add_argument("--click", default="", help="要点击的选项文本")
    ap.add_argument("--fuzzy", action="store_true", help="允许包含匹配")
    args = ap.parse_args()

    configure_human_pacing(ROOT / "config" / "human_pacing.json")
    c = create_helper(9225)
    try:
        result = c.eval(render_js(args.group or None, args.click or None, args.fuzzy))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.click:
            sleep_human(2.0)
            state = c.eval(S08_STATE_PROBE_JS)
            print(json.dumps(state, ensure_ascii=False, indent=2))
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
