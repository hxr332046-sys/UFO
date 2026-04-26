from __future__ import annotations

import json

SURVEY_JS = r"""
(function(){
  function norm(s){ return String(s || '').replace(/\s+/g, ' ').trim(); }
  function short(s, n){
    s = norm(s);
    if(!n || s.length <= n) return s;
    return s.slice(0, n);
  }
  function vis(el){
    if(!el) return false;
    try{
      var s = getComputedStyle(el);
      if(s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
    }catch(e){}
    try{
      return !!(el.offsetWidth || el.offsetHeight || (el.getClientRects && el.getClientRects().length));
    }catch(e){
      return false;
    }
  }
  function badText(t){
    return !t || /^page\d*$/i.test(t) || t === 'page' || t === 'page1';
  }
  function rectOf(el){
    try{
      var r = el.getBoundingClientRect();
      return {x: Math.round(r.x || 0), y: Math.round(r.y || 0), w: Math.round(r.width || 0), h: Math.round(r.height || 0)};
    }catch(e){
      return {x: 0, y: 0, w: 0, h: 0};
    }
  }
  function contextOf(el){
    var cur = null;
    try{
      cur = el.closest('.el-dialog,.el-dialog__wrapper,.el-message-box,.el-message-box__wrapper,.el-table__row,tr,li,.el-card,.page,.page1,.tne-data-picker-popover,.el-form-item,.zone-header-box-content-left,.zone-header-box-content-right,.app-main,#app');
    }catch(e){}
    if(!cur) cur = el.parentElement || el;
    return short((cur && cur.innerText) || '', 260);
  }
  function routeInfo(){
    try{
      var app = document.getElementById('app');
      if(app && app.__vue__ && app.__vue__.$route){
        var r = app.__vue__.$route;
        return {path: r.path || '', name: r.name || '', query: r.query || {}, params: r.params || {}};
      }
    }catch(e){}
    return null;
  }
  function detectPageType(href, hash){
    var route = String(hash || '').split('?')[0];
    href = String(href || '');
    if(href.indexOf('tyrz.zwfw.gxzf.gov.cn') >= 0) return 'sso_login';
    if(route.indexOf('enterprise-zone') >= 0) return 'enterprise_zone';
    if(route.indexOf('declaration-instructions') >= 0 || route.indexOf('namenotice') >= 0 || route.indexOf('name-notice') >= 0) return 'declaration_notice';
    if(route.indexOf('guide/base') >= 0) return 'guide_base';
    if(route.indexOf('space-index') >= 0 || route.indexOf('my-space') >= 0) return 'my_space';
    if(route.indexOf('namecheck') >= 0 || route.indexOf('name-check') >= 0) return 'name_check';
    if(route.indexOf('core/basic') >= 0 || route.indexOf('core/index') >= 0 || route.indexOf('/flow/base') >= 0) return 'core_basic_info';
    if(route.indexOf('my-cases') >= 0 || route.indexOf('banjian') >= 0) return 'my_cases';
    if(route.indexOf('index/page') >= 0 || route.indexOf('/index') >= 0) return 'portal';
    if(route.indexOf('login') >= 0 || href.indexOf('/login') >= 0) return 'login';
    return 'unknown';
  }
  function collectDialogs(){
    var wraps = Array.prototype.slice.call(document.querySelectorAll('.el-dialog__wrapper,.el-message-box__wrapper')).filter(vis);
    var out = [];
    for(var i=0;i<wraps.length;i++){
      var w = wraps[i];
      var title = '';
      var titleEl = w.querySelector('.el-dialog__title,.el-message-box__title');
      if(titleEl) title = norm(titleEl.innerText || titleEl.textContent || '');
      var body = '';
      var bodyEl = w.querySelector('.el-dialog__body,.el-message-box__content');
      if(bodyEl) body = short(bodyEl.innerText || bodyEl.textContent || '', 320);
      var buttons = Array.prototype.slice.call(w.querySelectorAll('button,.el-button')).filter(vis).map(function(b){
        return norm(b.innerText || b.textContent || '');
      }).filter(function(t){ return !badText(t); });
      if(title || body || buttons.length){
        out.push({title: title, body_preview: body, buttons: buttons});
      }
    }
    return out;
  }
  function collectInputs(){
    var nodes = Array.prototype.slice.call(document.querySelectorAll('input,textarea')).filter(vis);
    var out = [];
    for(var i=0;i<nodes.length && out.length < 30;i++){
      var el = nodes[i];
      out.push({
        index: out.length,
        tag: (el.tagName || '').toLowerCase(),
        type: (el.getAttribute('type') || '').toLowerCase(),
        placeholder: norm(el.getAttribute('placeholder') || el.placeholder || ''),
        value: short(el.value || '', 120),
        disabled: !!el.disabled,
        cls: String(el.className || '')
      });
    }
    return out;
  }
  function collectPickers(){
    var nodes = Array.prototype.slice.call(document.querySelectorAll('.tne-data-picker input.el-input__inner,.tne-data-picker input')).filter(vis);
    var out = [];
    for(var i=0;i<nodes.length && out.length < 12;i++){
      var el = nodes[i];
      out.push({
        index: out.length,
        placeholder: norm(el.getAttribute('placeholder') || el.placeholder || ''),
        value: short(el.value || '', 120),
        cls: String(el.className || '')
      });
    }
    return out;
  }
  function collectRadioGroups(){
    var groups = Array.prototype.slice.call(document.querySelectorAll('.tni-radio-group')).filter(vis);
    var out = [];
    for(var i=0;i<groups.length && out.length < 12;i++){
      var g = groups[i];
      var labels = Array.prototype.slice.call(g.querySelectorAll('label.tni-radio')).filter(vis);
      if(!labels.length) continue;
      var options = [];
      for(var j=0;j<labels.length;j++){
        var lb = labels[j];
        var inp = lb.querySelector('input');
        options.push({
          index: j,
          text: norm(lb.innerText || lb.textContent || ''),
          checked: String(lb.className || '').indexOf('is-checked') >= 0,
          value: inp ? String(inp.value || '') : '',
          cls: String(lb.className || '')
        });
      }
      var title = '';
      try{
        var parent = g.parentElement;
        if(parent){
          var full = norm(parent.innerText || '');
          var optText = options.map(function(x){ return x.text; }).join(' ');
          if(full && optText){
            var idx = full.indexOf(optText);
            if(idx > 0) title = short(full.slice(0, idx), 100);
          }
        }
      }catch(e){}
      if(!title){
        var prev = g.previousElementSibling;
        var hops = 0;
        while(prev && hops < 5 && !title){
          var t = norm(prev.innerText || prev.textContent || '');
          if(t && t.length <= 100) title = t;
          prev = prev.previousElementSibling;
          hops += 1;
        }
      }
      out.push({index: out.length, title: title, options: options});
    }
    return out;
  }
  function collectTableRows(){
    var nodes = Array.prototype.slice.call(document.querySelectorAll('tr,.el-table__row')).filter(vis);
    var out = [];
    var seen = {};
    for(var i=0;i<nodes.length && out.length < 15;i++){
      var row = nodes[i];
      var text = short(row.innerText || row.textContent || '', 420);
      if(!text) continue;
      var key = text.slice(0, 180);
      if(seen[key]) continue;
      seen[key] = true;
      var actions = Array.prototype.slice.call(row.querySelectorAll('button,.el-button,a,[role=button]')).filter(vis).map(function(b){
        return norm(b.innerText || b.textContent || '');
      }).filter(function(t){ return !badText(t); });
      out.push({index: out.length, text: text, actions: actions});
    }
    return out;
  }
  function collectActionables(){
    var pool = [];
    function push(type, el, disabled){
      if(!vis(el)) return;
      var text = norm(el.innerText || el.textContent || '');
      if(badText(text) || text.length > 80) return;
      var rc = rectOf(el);
      pool.push({
        el: el,
        row: {
          text: text,
          tag: String(el.tagName || '').toLowerCase(),
          cls: String(el.className || ''),
          type: type,
          disabled: !!disabled,
          context: contextOf(el),
          x: rc.x,
          y: rc.y,
          w: rc.w,
          h: rc.h
        }
      });
    }
    var btns = Array.prototype.slice.call(document.querySelectorAll('button,.el-button,a,[role=button]'));
    for(var i=0;i<btns.length;i++) push('button', btns[i], !!btns[i].disabled || btns[i].getAttribute('aria-disabled') === 'true');
    var radios = Array.prototype.slice.call(document.querySelectorAll('label.tni-radio.text-center,.tni-radio-group label.tni-radio'));
    for(var j=0;j<radios.length;j++) push('radio', radios[j], false);
    var pickerNodes = Array.prototype.slice.call(document.querySelectorAll('.tne-data-picker-popover .item,.tne-data-picker-popover .sample-item,.tne-data-picker-popover .item-text'));
    for(var k=0;k<pickerNodes.length;k++) push('picker_option', pickerNodes[k], false);
    pool.sort(function(a, b){
      if(a.row.y !== b.row.y) return a.row.y - b.row.y;
      if(a.row.x !== b.row.x) return a.row.x - b.row.x;
      return a.row.text.localeCompare(b.row.text);
    });
    var out = [];
    var els = [];
    var seen = {};
    for(var m=0;m<pool.length;m++){
      var item = pool[m];
      var key = [item.row.type, item.row.text, item.row.x, item.row.y].join('@');
      if(seen[key]) continue;
      seen[key] = true;
      item.row.index = out.length;
      out.push(item.row);
      els.push(item.el);
    }
    return {rows: out, els: els};
  }
  function collectErrors(){
    var errs = Array.prototype.slice.call(document.querySelectorAll('.el-form-item__error,.el-message--error,.el-alert--error')).filter(vis);
    var out = [];
    for(var i=0;i<errs.length && out.length < 20;i++){
      var t = norm(errs[i].innerText || errs[i].textContent || '');
      if(t) out.push(t);
    }
    return out;
  }
  function collectPrompts(text){
    var patterns = ['请确认您属于上述人员范围', '资格确认', '申报须知', '温馨提示', '请先完成', '统一认证', '登录'];
    var out = [];
    for(var i=0;i<patterns.length;i++) if(String(text || '').indexOf(patterns[i]) >= 0) out.push(patterns[i]);
    return out;
  }
  var actions = collectActionables();
  var pageText = short((document.body && document.body.innerText) || '', 1200);
  var visibleButtons = [];
  var seenButtons = {};
  for(var i=0;i<actions.rows.length;i++){
    var row = actions.rows[i];
    if(row.type !== 'button' || row.disabled || row.text.length >= 30) continue;
    if(seenButtons[row.text]) continue;
    seenButtons[row.text] = true;
    visibleButtons.push(row.text);
  }
  var recommended = [];
  var wants = ['开始办理', '我已阅读并同意', '继续办理', '下一步', '保存并下一步', '确定', '关闭'];
  var used = {};
  for(var j=0;j<wants.length;j++){
    for(var k=0;k<actions.rows.length;k++){
      var one = actions.rows[k];
      if(one.disabled) continue;
      if(one.text.indexOf(wants[j]) >= 0 && !used[one.index]){
        used[one.index] = true;
        recommended.push({index: one.index, text: one.text, type: one.type, context: one.context});
        break;
      }
    }
  }
  var result = {
    url: location.href,
    hash: location.hash,
    title: document.title,
    page_type: detectPageType(location.href, location.hash),
    visible_buttons: visibleButtons,
    actionables: actions.rows.slice(0, 60),
    recommended_actions: recommended,
    blocking_prompts: collectPrompts(pageText),
    dialogs: collectDialogs(),
    form_summary: {},
    error_messages: collectErrors(),
    vue_route: routeInfo(),
    login_ok: false,
    page_text_preview: pageText,
    visible_inputs: collectInputs(),
    picker_placeholders: collectPickers(),
    radio_groups: collectRadioGroups(),
    table_rows: collectTableRows()
  };
  try{
    result.login_ok = !!(localStorage.getItem('Authorization') && localStorage.getItem('top-token'));
  }catch(e){}
  return result;
})()
"""

CLICK_ACTION_JS = r"""
(function(targetIndex){
  function norm(s){ return String(s || '').replace(/\s+/g, ' ').trim(); }
  function vis(el){
    if(!el) return false;
    try{
      var s = getComputedStyle(el);
      if(s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
    }catch(e){}
    try{
      return !!(el.offsetWidth || el.offsetHeight || (el.getClientRects && el.getClientRects().length));
    }catch(e){
      return false;
    }
  }
  function badText(t){
    return !t || /^page\d*$/i.test(t) || t === 'page' || t === 'page1';
  }
  function rectOf(el){
    try{
      var r = el.getBoundingClientRect();
      return {x: Math.round(r.x || 0), y: Math.round(r.y || 0)};
    }catch(e){
      return {x: 0, y: 0};
    }
  }
  function contextOf(el){
    var cur = null;
    try{
      cur = el.closest('.el-dialog,.el-dialog__wrapper,.el-message-box,.el-message-box__wrapper,.el-table__row,tr,li,.el-card,.page,.page1,.tne-data-picker-popover,.el-form-item,.zone-header-box-content-left,.zone-header-box-content-right,.app-main,#app');
    }catch(e){}
    if(!cur) cur = el.parentElement || el;
    return norm((cur && cur.innerText) || '').slice(0, 260);
  }
  function collectActionables(){
    var pool = [];
    function push(type, el, disabled){
      if(!vis(el)) return;
      var text = norm(el.innerText || el.textContent || '');
      if(badText(text) || text.length > 80) return;
      var rc = rectOf(el);
      pool.push({
        el: el,
        row: {
          text: text,
          tag: String(el.tagName || '').toLowerCase(),
          cls: String(el.className || ''),
          type: type,
          disabled: !!disabled,
          context: contextOf(el),
          x: rc.x,
          y: rc.y
        }
      });
    }
    var btns = Array.prototype.slice.call(document.querySelectorAll('button,.el-button,a,[role=button]'));
    for(var i=0;i<btns.length;i++) push('button', btns[i], !!btns[i].disabled || btns[i].getAttribute('aria-disabled') === 'true');
    var radios = Array.prototype.slice.call(document.querySelectorAll('label.tni-radio.text-center,.tni-radio-group label.tni-radio'));
    for(var j=0;j<radios.length;j++) push('radio', radios[j], false);
    var pickerNodes = Array.prototype.slice.call(document.querySelectorAll('.tne-data-picker-popover .item,.tne-data-picker-popover .sample-item,.tne-data-picker-popover .item-text'));
    for(var k=0;k<pickerNodes.length;k++) push('picker_option', pickerNodes[k], false);
    pool.sort(function(a, b){
      if(a.row.y !== b.row.y) return a.row.y - b.row.y;
      if(a.row.x !== b.row.x) return a.row.x - b.row.x;
      return a.row.text.localeCompare(b.row.text);
    });
    var out = [];
    var els = [];
    var seen = {};
    for(var m=0;m<pool.length;m++){
      var item = pool[m];
      var key = [item.row.type, item.row.text, item.row.x, item.row.y].join('@');
      if(seen[key]) continue;
      seen[key] = true;
      item.row.index = out.length;
      out.push(item.row);
      els.push(item.el);
    }
    return {rows: out, els: els};
  }
  function fire(el){
    if(!el) return;
    try{ if(el.focus) el.focus(); }catch(e){}
    try{ el.click(); }catch(e){}
    try{ el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true, view:window})); }catch(e){}
    try{ el.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, cancelable:true, view:window})); }catch(e){}
    try{ el.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window})); }catch(e){}
  }
  var pack = collectActionables();
  if(typeof targetIndex !== 'number' || targetIndex < 0 || targetIndex >= pack.rows.length){
    return {ok:false, msg:'index_out_of_range', targetIndex:targetIndex, count:pack.rows.length, actionables:pack.rows.slice(0, 60)};
  }
  var el = pack.els[targetIndex];
  var row = pack.rows[targetIndex];
  fire(el);
  try{
    var label = el.querySelector && el.querySelector('.tni-radio__label');
    if(label) fire(label);
  }catch(e){}
  try{
    var inp = el.querySelector && el.querySelector('input');
    if(inp){
      try{ inp.checked = true; }catch(e){}
      fire(inp);
    }
  }catch(e){}
  return {ok:true, clicked:row, count:pack.rows.length};
})(%INDEX%)
"""


def render_click_action_js(index: int) -> str:
    return CLICK_ACTION_JS.replace("%INDEX%", json.dumps(int(index)))
