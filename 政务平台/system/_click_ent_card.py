"""Click '企业开办' card on 6087 TopIP and see where it goes."""
import json, time, requests, websocket

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
_id = [0]
def send_cdp(method, params=None):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == _id[0]:
            return msg.get("result", {})
def ev(expr):
    r = send_cdp("Runtime.evaluate", {"expression": expr, "returnByValue": True, "timeout": 20000})
    return r.get("result", {}).get("value")

# Ensure on 6087
href = ev("location.href")
if "6087" not in str(href):
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
    time.sleep(4)

# Check login state
print("=== Vuex login state ===")
login_state = ev("""(function(){
    var app = document.getElementById('app');
    var vm = app && app.__vue__;
    var store = vm && vm.$store;
    if (!store) return null;
    var login = store.state.login || {};
    return {
        token: login.token || '',
        userInfo: JSON.stringify(login.userInfo || {}).substring(0, 500),
    };
})()""")
print(json.dumps(login_state, ensure_ascii=False, indent=2))

# Find '企业开办' card at (468, 557) and explore its parent chain
print("\n=== '企业开办' card analysis ===")
analysis = ev("""(function(){
    var items = document.querySelectorAll('.item.is-collapsed, .item');
    var target = null;
    for (var i = 0; i < items.length; i++) {
        if (items[i].textContent.trim() === '企业开办') {
            var r = items[i].getBoundingClientRect();
            if (r.width > 0) { target = items[i]; break; }
        }
    }
    if (!target) return 'not found';
    
    // Walk up to find click handler or component
    var chain = [];
    var el = target;
    for (var d = 0; d < 10 && el; d++) {
        var listeners = [];
        try {
            var evts = getEventListeners(el);
            for (var k in evts) listeners.push(k + ':' + evts[k].length);
        } catch(e) {}
        chain.push({
            tag: el.tagName,
            cls: el.className.substring(0, 40),
            id: el.id,
            hasVueComponent: !!el.__vue__,
            componentName: el.__vue__ ? (el.__vue__.$options.name || el.__vue__.$options._componentTag || '') : '',
            listeners: listeners.join(','),
            dataset: JSON.stringify(el.dataset || {}).substring(0, 100),
        });
        el = el.parentElement;
    }
    return chain;
})()""")
print(json.dumps(analysis, ensure_ascii=False, indent=2))

# Find the Vue component data for the card
print("\n=== Card Vue component data ===")
card_data = ev("""(function(){
    var items = document.querySelectorAll('.item.is-collapsed, .item');
    var target = null;
    for (var i = 0; i < items.length; i++) {
        if (items[i].textContent.trim() === '企业开办') {
            var r = items[i].getBoundingClientRect();
            if (r.width > 0) { target = items[i]; break; }
        }
    }
    if (!target) return 'not found';
    
    // Find nearest Vue component
    var el = target;
    while (el && !el.__vue__) el = el.parentElement;
    if (!el) return 'no vue component found';
    
    var vm = el.__vue__;
    var result = {
        componentName: vm.$options.name || vm.$options._componentTag || '',
        data: {},
        props: {},
    };
    // Get data
    var d = vm.$data;
    for (var k in d) {
        var v = d[k];
        if (typeof v !== 'function') {
            result.data[k] = JSON.stringify(v).substring(0, 200);
        }
    }
    // Get props
    var p = vm.$props || {};
    for (var k2 in p) {
        result.props[k2] = JSON.stringify(p[k2]).substring(0, 200);
    }
    
    return result;
})()""")
print(json.dumps(card_data, ensure_ascii=False, indent=2))

# Now intercept click and monitor navigation
print("\n=== Clicking '企业开办' card ===")
send_cdp("Network.enable")

# Click the visible card
ev("""(function(){
    var items = document.querySelectorAll('.item.is-collapsed, .item');
    for (var i = 0; i < items.length; i++) {
        if (items[i].textContent.trim() === '企业开办') {
            var r = items[i].getBoundingClientRect();
            if (r.width > 0) {
                items[i].click();
                return 'clicked at ' + r.x + ',' + r.y;
            }
        }
    }
    return 'not found';
})()""")

# Monitor
for i in range(15):
    time.sleep(2)
    try:
        href = ev("location.href")
        auth = ev("localStorage.getItem('Authorization') || ''")
    except:
        print(f"  [{i+1}] (redirecting...)")
        continue
    print(f"  [{i+1}] {href[:80]} auth={'YES' if auth else 'none'}")
    if "9087" in str(href) and auth:
        print(f"  >>> ON 9087 WITH AUTH: {auth[:30]}...")
        break

ws.close()
