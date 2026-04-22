#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests
import websocket

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from human_pacing import configure_human_pacing  # noqa: E402

HOST = "zhjg.scjdglj.gxzf.gov.cn:9087"
OUT = ROOT / "dashboard" / "data" / "records" / "guide_base_ent_type_hierarchy_latest.json"

SURVEY_JS = r'''(async function(){
  function sleep(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }
  function clean(s){ return (s||'').replace(/\s+/g,' ').trim(); }
  function vis(e){
    if(!e) return false;
    var s = getComputedStyle(e);
    return s.display !== 'none' && s.visibility !== 'hidden' && (e.offsetWidth > 0 || e.offsetHeight > 0);
  }
  function walk(vm, d, pred){
    if(!vm || d > 24) return null;
    try{ if(pred(vm)) return vm; }catch(e){}
    var ch = vm.$children || [];
    for(var i=0;i<ch.length;i++){
      var r = walk(ch[i], d+1, pred);
      if(r) return r;
    }
    return null;
  }
  function parseText(raw){
    var t = clean(raw);
    var m = t.match(/^\[(\d{4})\](.+)$/);
    if(!m) return null;
    return {code:m[1], name:clean(m[2]), text:'[' + m[1] + ']' + clean(m[2])};
  }
  function guessNode(x){
    var rawName = clean(
      x && (
        x.name || x.label || x.text || x.title || x.dictLabel || x.itemName || x.mc || x.typeName || x.fullName || x.displayName || ''
      )
    );
    var rawCode = clean(
      x && (
        x.code || x.value || x.uniqueId || x.id || x.dm || x.typeCode || x.itemCode || x.dictValue || ''
      )
    );
    var p1 = parseText(rawName);
    if(p1) return {code:p1.code, name:p1.name, text:p1.text, isLeaf:!!(x && x.isLeaf)};
    var p2 = parseText(rawCode);
    if(p2) return {code:p2.code, name:p2.name, text:p2.text, isLeaf:!!(x && x.isLeaf)};
    if(/^\d{4}$/.test(rawCode) && rawName){
      return {code:rawCode, name:rawName.replace(/^\[\d{4}\]/, ''), text:'[' + rawCode + ']' + rawName.replace(/^\[\d{4}\]/, ''), isLeaf:!!(x && x.isLeaf)};
    }
    return null;
  }
  function sameItems(a,b){
    if(!Array.isArray(a) || !Array.isArray(b)) return false;
    if(a.length !== b.length) return false;
    for(var i=0;i<a.length;i++){
      if((a[i]||{}).text !== (b[i]||{}).text) return false;
    }
    return true;
  }
  function getGuideVm(){
    var app = document.getElementById('app');
    return app && app.__vue__ ? walk(app.__vue__, 0, function(v){
      var n = (v.$options && v.$options.name) || '';
      return n === 'index' && typeof v.flowSave === 'function';
    }) : null;
  }
  function getPickerVm(){
    var guide = getGuideVm();
    return guide ? walk(guide, 0, function(v){
      if((v.$options && v.$options.name) !== 'tne-data-picker') return false;
      var ph = clean(v.placeholder || ((v.$props || {}).placeholder) || '');
      if(ph.indexOf('企业类型') >= 0) return true;
      try{
        var inp = v.$el && v.$el.querySelector ? v.$el.querySelector('input') : null;
        var domPh = clean(inp && inp.getAttribute ? (inp.getAttribute('placeholder') || '') : '');
        return domPh.indexOf('企业类型') >= 0;
      }catch(e){
        return false;
      }
    }) : null;
  }
  function currentItemsFromPicker(){
    var p = getPickerVm();
    if(!p) return [];
    var dl = Array.isArray(p.dataList) ? p.dataList : [];
    if(!dl.length) return [];
    var arr = dl[dl.length - 1];
    if(!Array.isArray(arr)) return [];
    var out = [];
    var seen = {};
    for(var i=0;i<arr.length;i++){
      var x = arr[i] || {};
      var g = guessNode(x);
      if(!g || !g.text) continue;
      if(seen[g.text]) continue;
      seen[g.text] = true;
      out.push(g);
    }
    return out;
  }
  function currentItemsFromDom(){
    var pop = [].slice.call(document.querySelectorAll('.tne-data-picker-popover')).find(function(p){ return vis(p); });
    if(!pop) return [];
    var nodes = [].slice.call(pop.querySelectorAll('.item,.item-text,.sample-item'));
    var out = [];
    var seen = {};
    for(var i=0;i<nodes.length;i++){
      var t = clean(nodes[i].textContent || '');
      var p1 = parseText(t);
      if(!p1) continue;
      if(seen[p1.text]) continue;
      seen[p1.text] = true;
      out.push({code:p1.code, name:p1.name, text:p1.text});
    }
    return out;
  }
  function currentItems(){
    var a = currentItemsFromPicker();
    return a.length ? a : currentItemsFromDom();
  }
  function clickAllTypes(){
    var nodes = [].slice.call(document.querySelectorAll('label.tni-radio.text-center,.tni-radio__label,label,span'))
      .filter(function(e){ return vis(e); });
    var exact = nodes.find(function(e){ return clean(e.textContent || '') === '全部企业类型'; });
    var fuzzy = nodes.find(function(e){
      var t = clean(e.textContent || '');
      return t.indexOf('全部企业类型') >= 0 && t.length <= 12;
    });
    var hit = exact || fuzzy;
    if(!hit) return {ok:false, msg:'all_types_not_found'};
    hit.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window}));
    return {ok:true, hit:clean(hit.textContent || ''), cls:(hit.className || '') + ''};
  }
  function openEntTypePicker(){
    var p = getPickerVm();
    if(p && p.$el){
      try{
        var ref = p.$el.querySelector('.el-popover__reference,.tne-data-picker__input,.el-input__inner,input');
        if(ref){
          ref.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window}));
          return {ok:true, mode:'picker_vm_dom'};
        }
      }catch(e){}
    }
    var inp = [].slice.call(document.querySelectorAll('input.el-input__inner,input')).find(function(x){
      return vis(x) && clean(x.getAttribute('placeholder') || x.placeholder || '') === '请选择企业类型';
    });
    if(inp){
      inp.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window}));
      return {ok:true, mode:'input_placeholder'};
    }
    return {ok:false, msg:'ent_type_picker_input_not_found'};
  }
  function setPickerRoot(){
    var p = getPickerVm();
    if(!p) return {ok:false, msg:'no_picker'};
    try{
      if(Array.isArray(p.treeData) && p.treeData.length){
        try{ p.selected = []; }catch(e){}
        try{ p.inputSelected = []; }catch(e){}
        try{ p.checkValue = []; }catch(e){}
        try{ p.selectedIndex = 0; }catch(e){}
        try{ p.dataList = [p.treeData]; }catch(e){}
        try{ p.isOpened = true; }catch(e){}
        return {ok:true, rootCount:p.treeData.length, dataListLen:(p.dataList || []).length};
      }
    }catch(e){
      return {ok:false, msg:e.message || String(e)};
    }
    return {ok:false, msg:'treeData_empty'};
  }
  function clickCurrentItem(text){
    var pop = [].slice.call(document.querySelectorAll('.tne-data-picker-popover')).find(function(p){ return vis(p); });
    var nodes = pop
      ? [].slice.call(pop.querySelectorAll('.item,.item-text,.sample-item,span,div')).filter(function(e){ return vis(e); })
      : [];
    var exactItem = nodes.find(function(e){
      return clean(e.textContent || '') === text && ((e.className || '') + '').indexOf('item') >= 0;
    });
    var exact = nodes.find(function(e){ return clean(e.textContent || '') === text; });
    var fuzzy = nodes.find(function(e){
      var t = clean(e.textContent || '');
      return t.indexOf(text) >= 0 && t.length <= Math.max(18, text.length + 6);
    });
    var hit = exactItem || exact || fuzzy;
    if(!hit) return {ok:false, msg:'not_found', want:text};
    hit.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window}));
    return {ok:true, hit:clean(hit.textContent || ''), cls:(hit.className || '') + ''};
  }
  async function ensureRoot(){
    var log = [];
    var items = currentItems();
    if(items.length && items[0].code === '1000') return {ok:true, items:items, log:log};
    var r0 = clickAllTypes();
    log.push({step:'click_all_types', data:r0});
    await sleep(500);
    var r1 = openEntTypePicker();
    log.push({step:'open_ent_type_picker', data:r1});
    await sleep(900);
    var r2 = setPickerRoot();
    log.push({step:'set_root_direct', data:r2});
    await sleep(300);
    items = currentItems();
    if(items.length && items[0].code === '1000') return {ok:true, items:items, log:log};
    var r3 = openEntTypePicker();
    log.push({step:'reopen_ent_type_picker', data:r3});
    await sleep(900);
    items = currentItems();
    if(items.length && items[0].code === '1000') return {ok:true, items:items, log:log};
    var r4 = setPickerRoot();
    log.push({step:'set_root_after_open', data:r4});
    await sleep(300);
    items = currentItems();
    if(items.length && items[0].code === '1000') return {ok:true, items:items, log:log};
    return {ok:false, msg:'root_not_ready', items:items, log:log};
  }
  async function navigate(path){
    var root = await ensureRoot();
    if(!root.ok) return {ok:false, step:'ensure_root', detail:root};
    if(!path || !path.length) return {ok:true, items:root.items, leaf:false, steps:[]};
    var steps = [];
    var lastBefore = root.items;
    for(var i=0;i<path.length;i++){
      lastBefore = currentItems();
      var clicked = clickCurrentItem(path[i]);
      steps.push({want:path[i], click:clicked, beforeCount:lastBefore.length});
      if(!clicked.ok) return {ok:false, step:'click', index:i, steps:steps, current:lastBefore};
      await sleep(1000);
    }
    var after = currentItems();
    var leaf = !after.length || sameItems(after, lastBefore);
    return {ok:true, items:leaf ? [] : after, leaf:leaf, steps:steps};
  }
  async function surveyLevel(path, level, errors, stats){
    if(level > 4) return [];
    var nav = path.length ? await navigate(path) : await ensureRoot();
    if(!nav.ok){
      errors.push({path:path, level:level, nav:nav});
      return [];
    }
    var items = nav.items || [];
    if(!items.length) return [];
    var nodes = [];
    for(var i=0;i<items.length;i++){
      stats.visited += 1;
      var item = items[i];
      var node = {
        level: level,
        code: item.code,
        name: item.name,
        text: item.text,
        path: path.concat([item.text]),
        children: []
      };
      if(level < 4){
        node.children = await surveyLevel(node.path, level + 1, errors, stats);
      }
      nodes.push(node);
    }
    return nodes;
  }
  function flatten(nodes, row, rows){
    for(var i=0;i<nodes.length;i++){
      var n = nodes[i];
      var cur = Object.assign({}, row);
      cur['level' + n.level + '_code'] = n.code;
      cur['level' + n.level + '_name'] = n.name;
      if(n.children && n.children.length){
        flatten(n.children, cur, rows);
      }else{
        rows.push(cur);
      }
    }
  }
  function getGuideState(){
    var guide = getGuideVm();
    var p = getPickerVm();
    return {
      choiceName: guide ? (guide.choiceName || '') : '',
      entTypeCode: guide ? (guide.entTypeCode || '') : '',
      entTypeRealy: guide ? (guide.entTypeRealy || '') : '',
      form: guide && guide.form ? {
        entType: guide.form.entType || '',
        nameCode: guide.form.nameCode || '',
        isnameType: guide.form.isnameType || '',
        choiceName: guide.form.choiceName || '',
        havaAdress: guide.form.havaAdress || '',
        distCode: guide.form.distCode || ''
      } : null,
      picker: p ? {
        checkValue: Array.isArray(p.checkValue) ? p.checkValue.slice(0,8) : p.checkValue,
        dataListLen: Array.isArray(p.dataList) ? p.dataList.length : 0,
        treeDataLen: Array.isArray(p.treeData) ? p.treeData.length : 0,
        isOpened: !!p.isOpened,
        rawSample: pickerRawSample(8)
      } : null
    };
  }
  function pickerRawSample(limit){
    var p = getPickerVm();
    if(!p) return [];
    var td = Array.isArray(p.treeData) ? p.treeData : [];
    var out = [];
    for(var i=0;i<Math.min(limit || 8, td.length);i++){
      var x = td[i] || {};
      var keys = Object.keys(x).slice(0, 20);
      var g = guessNode(x);
      out.push({
        keys: keys,
        guessed: g,
        preview: JSON.stringify(x).slice(0, 300)
      });
    }
    return out;
  }
  function restoreBlank(before){
    var guide = getGuideVm();
    var p = getPickerVm();
    try{
      if(guide && guide.form && before && before.form){
        if(typeof guide.$set === 'function'){
          guide.$set(guide.form, 'entType', before.form.entType || '');
          guide.$set(guide.form, 'nameCode', before.form.nameCode || '');
          guide.$set(guide.form, 'isnameType', before.form.isnameType || '');
          guide.$set(guide.form, 'choiceName', before.form.choiceName || '');
          guide.$set(guide.form, 'havaAdress', before.form.havaAdress || '');
          guide.$set(guide.form, 'distCode', before.form.distCode || '');
        }else{
          guide.form.entType = before.form.entType || '';
          guide.form.nameCode = before.form.nameCode || '';
          guide.form.isnameType = before.form.isnameType || '';
          guide.form.choiceName = before.form.choiceName || '';
          guide.form.havaAdress = before.form.havaAdress || '';
          guide.form.distCode = before.form.distCode || '';
        }
      }
      if(guide){
        guide.choiceName = before && typeof before.choiceName === 'string' ? before.choiceName : '';
        if(before && typeof before.entTypeCode === 'string') guide.entTypeCode = before.entTypeCode;
        if(before && typeof before.entTypeRealy === 'string') guide.entTypeRealy = before.entTypeRealy;
      }
      if(p){
        p.selected = [];
        p.inputSelected = [];
        p.checkValue = before && before.picker ? (before.picker.checkValue || []) : [];
        p.selectedIndex = 0;
        if(Array.isArray(p.treeData) && p.treeData.length) p.dataList = [p.treeData];
        p.isOpened = false;
      }
      try{ document.body.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window})); }catch(e){}
      return {ok:true};
    }catch(e){
      return {ok:false, error:e.message || String(e)};
    }
  }
  var before = getGuideState();
  var errors = [];
  var stats = {visited:0};
  var rootReady = await ensureRoot();
  var built = buildTreeFromRaw();
  var tree = [];
  if(built.root_count > 0 && built.linked_count > 0){
    tree = trimTree(built.roots, 1, []);
    stats.visited = built.raw_count;
  }else{
    if(!(rootReady && rootReady.ok)) errors.push({path:[], level:1, nav:rootReady});
    tree = await surveyLevel([], 1, errors, stats);
  }
  var flat = [];
  flatten(tree, {}, flat);
  var restored = restoreBlank(before);
  await sleep(300);
  return {
    ok: true,
    href: location.href,
    before: before,
    method: (built.root_count > 0 && built.linked_count > 0) ? 'treeData_parent_link' : 'dom_fallback',
    root_ready: rootReady,
    raw_build: {
      raw_count: built.raw_count,
      root_count: built.root_count,
      linked_count: built.linked_count,
      sample: built.sample
    },
    tree: tree,
    flat_rows: flat,
    stats: {
      visited: stats.visited,
      root_count: Array.isArray(tree) ? tree.length : 0,
      flat_count: flat.length
    },
    restored: restored,
    after: getGuideState(),
    errors: errors
  };
})()'''


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    for p in pages:
        if p.get("type") == "page" and HOST.split(":")[0] in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url: str, expr: str, timeout_ms: int = 240000):
    wall = max(20, timeout_ms / 1000 + 20)
    ws = websocket.create_connection(ws_url, timeout=25)
    ws.settimeout(2.0)
    try:
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expr,
                        "returnByValue": True,
                        "awaitPromise": True,
                        "timeout": timeout_ms,
                    },
                }
            )
        )
        deadline = time.time() + wall
        while time.time() < deadline:
            try:
                m = json.loads(ws.recv())
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                continue
            if m.get("id") != 1:
                continue
            if m.get("error"):
                return {"ok": False, "cdp_error": m.get("error")}
            res = m.get("result") or {}
            if res.get("exceptionDetails"):
                det = res.get("exceptionDetails") or {}
                return {
                    "ok": False,
                    "exception": det.get("text") or "Runtime exception",
                    "lineNumber": det.get("lineNumber"),
                    "columnNumber": det.get("columnNumber"),
                }
            obj = res.get("result") or {}
            if "value" in obj:
                return obj.get("value")
            return obj
        return {"ok": False, "timeout": True, "wall": wall}
    finally:
        try:
            ws.close()
        except Exception:
            pass


def main() -> int:
    configure_human_pacing(ROOT / "config" / "human_pacing.json")
    ws_url, cur = pick_ws()
    rec = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "current_url": cur,
        "script": str(Path(__file__).name),
    }
    if not ws_url:
        rec["ok"] = False
        rec["error"] = "guide_base_tab_missing"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        print("ERROR: guide_base_tab_missing")
        return 2
    result = ev(ws_url, SURVEY_JS, timeout_ms=420000)
    rec["result"] = result
    rec["ok"] = bool(isinstance(result, dict) and result.get("ok"))
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")
    if isinstance(result, dict):
        stats = result.get("stats") or {}
        print(json.dumps({
            "ok": result.get("ok"),
            "root_count": stats.get("root_count"),
            "flat_count": stats.get("flat_count"),
            "visited": stats.get("visited"),
            "errors": len(result.get("errors") or []),
            "restored": result.get("restored"),
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if rec["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
