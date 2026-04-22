"""Expand '经营主体登记' section and click '企业开办' on 6087 TopIP to enter 9087."""
import json, time, requests, websocket
from pathlib import Path

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
_id = [0]
_events = []
def send_cdp(method, params=None):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("method"):
            _events.append(msg)
        if msg.get("id") == _id[0]:
            return msg.get("result", {})
def ev(expr):
    r = send_cdp("Runtime.evaluate", {"expression": expr, "returnByValue": True, "timeout": 20000})
    return r.get("result", {}).get("value")

# Navigate to 6087
href = ev("location.href")
if "6087" not in str(href):
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
    time.sleep(5)

# Step 1: Expand the '经营主体登记' section by clicking the header
print("=== Step 1: Expand section ===")
result = ev("""(function(){
    // Find the collapse-service component for '经营主体登记'
    var items = document.querySelectorAll('.collapse-service, [class*=collapse]');
    for (var i = 0; i < items.length; i++) {
        if (items[i].textContent.indexOf('经营主体登记') >= 0 && items[i].textContent.indexOf('企业开办') >= 0) {
            // Find the header/title element and click it
            var header = items[i].querySelector('.title, .header, h3, h4');
            if (header) {
                header.click();
                return 'clicked header: ' + header.textContent.trim().substring(0, 30);
            }
            // Try clicking the item itself
            items[i].click();
            return 'clicked container';
        }
    }
    // Try broader search
    var divs = document.querySelectorAll('div');
    for (var j = 0; j < divs.length; j++) {
        var d = divs[j];
        if (d.textContent.trim() === '经营主体登记' && d.getBoundingClientRect().width > 50) {
            d.click();
            return 'clicked div: ' + d.className;
        }
    }
    return 'not found';
})()""")
print(f"  {result}")
time.sleep(1)

# Step 2: Now find all visible sub-items
print("\n=== Step 2: Find sub-items ===")
sub_items = ev("""(function(){
    var results = [];
    var items = document.querySelectorAll('.item, .card, .service-item, a, [class*=item]');
    for (var i = 0; i < items.length; i++) {
        var el = items[i];
        var text = el.textContent.trim();
        var r = el.getBoundingClientRect();
        if (r.width > 20 && r.height > 10 && text.length < 20 && text.length > 2 && r.y > 100) {
            if (text.indexOf('企业') >= 0 || text.indexOf('变更') >= 0 || text.indexOf('注销') >= 0 ||
                text.indexOf('迁移') >= 0 || text.indexOf('个体') >= 0 || text.indexOf('备案') >= 0 ||
                text.indexOf('登记') >= 0 || text.indexOf('开办') >= 0) {
                results.push({
                    text: text.substring(0, 20),
                    tag: el.tagName,
                    cls: el.className.substring(0, 30),
                    x: r.x + r.width/2,
                    y: r.y + r.height/2,
                    w: r.width,
                    h: r.height,
                    visible: el.offsetParent !== null,
                    href: el.href || '',
                });
            }
        }
    }
    return results;
})()""")
for item in (sub_items or []):
    print(f"  '{item['text']}' {item['tag']}.{item['cls']} ({item['x']:.0f},{item['y']:.0f}) {item['w']:.0f}x{item['h']:.0f} href={item['href'][:60]}")

# Step 3: Find and click '企业开办' - the SPECIFIC small text element
print("\n=== Step 3: Click '企业开办' ===")
send_cdp("Network.enable")
_events.clear()

# Find Vue component with data
click_result = ev("""(function(){
    // First, look at the collapsed service data
    var app = document.getElementById('app');
    var vm = app.__vue__;
    // Recursively find collapse-service components
    function findComp(v, name) {
        if (v.$options.name === name || v.$options._componentTag === name) return v;
        for (var i = 0; i < (v.$children || []).length; i++) {
            var r = findComp(v.$children[i], name);
            if (r) return r;
        }
        return null;
    }
    var cs = findComp(vm, 'collapse-service');
    if (!cs) return 'collapse-service not found';
    
    // Get the data items
    var items = cs.data || cs.$props.data || [];
    var result = items.map(function(item) {
        return {
            name: item.name || item.title || item.bizName || '',
            url: item.url || item.appUrl || item.path || item.redirectUrl || '',
            code: item.code || item.bizCode || item.appCode || '',
            id: item.id || '',
        };
    });
    return result;
})()""")
print(f"  Service data: {json.dumps(click_result, ensure_ascii=False)[:500]}")

# Also get ALL collapse-service components
print("\n=== All collapse-service components ===")
all_cs = ev("""(function(){
    var app = document.getElementById('app');
    var vm = app.__vue__;
    var results = [];
    function findAll(v, name) {
        if (v.$options.name === name || v.$options._componentTag === name) results.push(v);
        for (var i = 0; i < (v.$children || []).length; i++) findAll(v.$children[i], name);
    }
    findAll(vm, 'collapse-service');
    return results.map(function(cs) {
        var d = cs.data || cs.$props.data || [];
        return {
            title: cs.title || cs.$props.title || '',
            collapsed: cs.collapsed,
            items: d.map(function(item) {
                var keys = Object.keys(item).filter(function(k){ return typeof item[k] === 'string' && item[k].length > 0 && item[k].length < 200; });
                var obj = {};
                keys.forEach(function(k){ obj[k] = item[k]; });
                return obj;
            })
        };
    });
})()""")
for cs in (all_cs or []):
    print(f"\n  Section: '{cs.get('title', '')}' collapsed={cs.get('collapsed')}")
    for item in cs.get('items', []):
        print(f"    {json.dumps(item, ensure_ascii=False)[:200]}")

ws.close()
