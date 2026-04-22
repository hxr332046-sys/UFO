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


OPEN_PICKER_JS = r"""
(function(placeholderText){
  function norm(s){ return String(s || '').replace(/\s+/g, ' ').trim(); }
  function vis(e){
    if(!e) return false;
    var s = getComputedStyle(e);
    return s.display !== 'none' && s.visibility !== 'hidden' && (e.offsetWidth > 0 || e.offsetHeight > 0);
  }
  function findInput(){
    var inputs = Array.prototype.slice.call(document.querySelectorAll('.tne-data-picker input.el-input__inner, .tne-data-picker input')).filter(vis);
    for(var i=0;i<inputs.length;i++){
      var ph = norm(inputs[i].getAttribute('placeholder') || inputs[i].placeholder || '');
      if(ph === placeholderText) return inputs[i];
    }
    for(var j=0;j<inputs.length;j++){
      var ph2 = norm(inputs[j].getAttribute('placeholder') || inputs[j].placeholder || '');
      if(ph2.indexOf(placeholderText) >= 0) return inputs[j];
    }
    return null;
  }
  function openPicker(){
    var inp = findInput();
    if(!inp) return {ok:false, msg:'picker_input_not_found', placeholder:placeholderText};
    try{ inp.click(); }catch(e){}
    try{ inp.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window})); }catch(e){}
    return {ok:true, placeholder:norm(inp.getAttribute('placeholder') || inp.placeholder || '')};
  }
  return openPicker();
})(%PLACEHOLDER%)
"""


READ_OPTIONS_JS = r"""
(function(){
  function norm(s){ return String(s || '').replace(/\s+/g, ' ').trim(); }
  function vis(e){
    if(!e) return false;
    var s = getComputedStyle(e);
    return s.display !== 'none' && s.visibility !== 'hidden' && (e.offsetWidth > 0 || e.offsetHeight > 0);
  }
  function getPopover(){
    return Array.prototype.slice.call(document.querySelectorAll('.tne-data-picker-popover')).find(function(p){ return vis(p); }) || null;
  }
  function currentOptions(){
    var pop = getPopover();
    if(!pop) return [];
    var nodes = Array.prototype.slice.call(pop.querySelectorAll('.item,.sample-item,.item-text'));
    var out = [];
    var seen = {};
    for(var i=0;i<nodes.length;i++){
      var el = nodes[i];
      if(!vis(el)) continue;
      var text = norm(el.textContent || '');
      if(!text || text.length > 60) continue;
      var rect = el.getBoundingClientRect();
      var key = text + '@' + Math.round(rect.x) + '@' + Math.round(rect.y);
      if(seen[key]) continue;
      seen[key] = true;
      out.push({text:text, cls:(el.className || '') + '', x:Math.round(rect.x), y:Math.round(rect.y)});
    }
    return out;
  }
  return currentOptions();
})()
"""


CLICK_OPTION_JS = r"""
(function(want){
  function norm(s){ return String(s || '').replace(/\s+/g, ' ').trim(); }
  function vis(e){
    if(!e) return false;
    var s = getComputedStyle(e);
    return s.display !== 'none' && s.visibility !== 'hidden' && (e.offsetWidth > 0 || e.offsetHeight > 0);
  }
  function getPopover(){
    return Array.prototype.slice.call(document.querySelectorAll('.tne-data-picker-popover')).find(function(p){ return vis(p); }) || null;
  }
  function currentOptions(){
    var pop = getPopover();
    if(!pop) return [];
    var nodes = Array.prototype.slice.call(pop.querySelectorAll('.item,.sample-item,.item-text'));
    var out = [];
    var seen = {};
    for(var i=0;i<nodes.length;i++){
      var el = nodes[i];
      if(!vis(el)) continue;
      var text = norm(el.textContent || '');
      if(!text || text.length > 60) continue;
      var rect = el.getBoundingClientRect();
      var key = text + '@' + Math.round(rect.x) + '@' + Math.round(rect.y);
      if(seen[key]) continue;
      seen[key] = true;
      out.push({text:text, cls:(el.className || '') + '', x:Math.round(rect.x), y:Math.round(rect.y)});
    }
    return out;
  }
  function clickOption(want){
    var pop = getPopover();
    if(!pop) return {ok:false, msg:'no_popover', want:want};
    var nodes = Array.prototype.slice.call(pop.querySelectorAll('.item,.sample-item,.item-text')).filter(vis);
    var exact = null;
    var fuzzy = null;
    for(var i=0;i<nodes.length;i++){
      var t = norm(nodes[i].textContent || '');
      if(!t || t.length > 60) continue;
      if(t === want){
        if(!exact || t.length < norm(exact.textContent || '').length) exact = nodes[i];
      }
      if(t.indexOf(want) >= 0 && t.length <= Math.max(18, want.length + 8)){
        if(!fuzzy || t.length < norm(fuzzy.textContent || '').length) fuzzy = nodes[i];
      }
    }
    var hit = exact || fuzzy;
    if(!hit) return {ok:false, msg:'option_not_found', want:want, options:currentOptions()};
    var text = norm(hit.textContent || '');
    try{ hit.click(); }catch(e){}
    try{ hit.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window})); }catch(e){}
    return {ok:true, want:want, hit:text, cls:(hit.className || '') + ''};
  }
  return {ok:true, click:clickOption(want), after:currentOptions()};
})(%WANT%)
"""


def render_open_js(placeholder: str) -> str:
    return OPEN_PICKER_JS.replace("%PLACEHOLDER%", json.dumps(placeholder, ensure_ascii=False))


def render_click_js(want: str) -> str:
    return CLICK_OPTION_JS.replace("%WANT%", json.dumps(want, ensure_ascii=False))


def main() -> int:
    ap = argparse.ArgumentParser(description="通用 tne-data-picker 单步探测/选择")
    ap.add_argument("--placeholder", required=True, help="input placeholder 文本")
    ap.add_argument("--pick", nargs="*", default=[], help="依次点击的选项文本")
    args = ap.parse_args()

    configure_human_pacing(ROOT / "config" / "human_pacing.json")
    c = create_helper(9225)
    try:
        result = {
            "placeholder": args.placeholder,
            "open": c.eval(render_open_js(args.placeholder)),
        }
        sleep_human(1.2)
        result["before"] = c.eval(READ_OPTIONS_JS)
        steps = []
        for pick in args.pick:
            step = {
                "want": pick,
                "before": c.eval(READ_OPTIONS_JS),
                "click": c.eval(render_click_js(pick)),
            }
            sleep_human(1.2)
            step["after"] = c.eval(READ_OPTIONS_JS)
            steps.append(step)
        result["steps"] = steps
        result["final"] = c.eval(READ_OPTIONS_JS)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.pick:
            sleep_human(2.0)
            state = c.eval(S08_STATE_PROBE_JS)
            print(json.dumps(state, ensure_ascii=False, indent=2))
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
