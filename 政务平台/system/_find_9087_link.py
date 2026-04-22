"""Find how 6087 TopIP navigates to 9087 ICPSP."""
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

# Make sure we're on 6087
href = ev("location.href")
if "6087" not in str(href):
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
    time.sleep(4)

# Search for anything referencing 9087 or icpsp
print("=== Search for 9087/icpsp references ===")
refs = ev("""(function(){
    var html = document.documentElement.outerHTML;
    var results = [];
    // Find all URLs containing 9087
    var matches = html.match(/https?:\/\/[^"'\\s<>]+9087[^"'\\s<>]*/gi);
    if (matches) results.push({type: 'url_9087', items: matches.slice(0, 10)});
    // Find icpsp references
    var icpsp = html.match(/icpsp[^"'\\s<>]*/gi);
    if (icpsp) results.push({type: 'icpsp', items: [...new Set(icpsp)].slice(0, 10)});
    return results;
})()""")
for r in (refs or []):
    print(f"\n{r['type']}:")
    for item in r['items']:
        print(f"  {item[:100]}")

# Look at Vue router configuration
print("\n=== Vue Router routes ===")
routes = ev("""(function(){
    var app = document.getElementById('app');
    var vm = app && app.__vue__;
    if (!vm || !vm.$router) return 'no router';
    var routes = vm.$router.options.routes || [];
    function flatRoutes(rs, prefix) {
        var result = [];
        for (var i = 0; i < rs.length; i++) {
            var r = rs[i];
            result.push({path: prefix + (r.path || ''), name: r.name || '', meta: r.meta || {}});
            if (r.children) {
                result = result.concat(flatRoutes(r.children, prefix + (r.path || '') + '/'));
            }
        }
        return result;
    }
    return flatRoutes(routes, '').slice(0, 30);
})()""")
if isinstance(routes, list):
    for r in routes:
        meta = json.dumps(r.get('meta', {}), ensure_ascii=False)[:60]
        print(f"  {r.get('path', '')} name={r.get('name', '')} meta={meta}")
else:
    print(f"  {routes}")

# Look at Vuex store for app configuration 
print("\n=== TopIP app config/menu ===")
menu = ev("""(function(){
    var app = document.getElementById('app');
    var vm = app && app.__vue__;
    var store = vm && vm.$store;
    if (!store) return null;
    var state = store.state;
    // Look for menu/app config
    var result = {};
    for (var key in state) {
        var v = state[key];
        if (typeof v === 'object' && v !== null) {
            var keys = Object.keys(v);
            result[key] = keys.slice(0, 20).join(', ');
        }
    }
    return result;
})()""")
print(json.dumps(menu, ensure_ascii=False, indent=2))

# Check specific store module for app URLs
print("\n=== Framework/index state ===")
fw_state = ev("""(function(){
    var app = document.getElementById('app');
    var vm = app && app.__vue__;
    var store = vm && vm.$store;
    if (!store) return null;
    var fw = store.state.framework || {};
    var idx = store.state.index || {};
    // Find anything with URLs
    function findUrls(obj, prefix, depth) {
        var result = {};
        if (depth > 2) return result;
        for (var k in obj) {
            if (!obj.hasOwnProperty(k)) continue;
            var v = obj[k];
            if (typeof v === 'string' && (v.indexOf('http') >= 0 || v.indexOf('9087') >= 0 || v.indexOf('portal') >= 0)) {
                result[prefix + k] = v;
            } else if (Array.isArray(v) && v.length > 0 && v.length < 5) {
                for (var i = 0; i < v.length; i++) {
                    if (typeof v[i] === 'object') {
                        var sub = findUrls(v[i], prefix + k + '[' + i + '].', depth + 1);
                        for (var sk in sub) result[sk] = sub[sk];
                    }
                }
            } else if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
                var sub2 = findUrls(v, prefix + k + '.', depth + 1);
                for (var sk2 in sub2) result[sk2] = sub2[sk2];
            }
        }
        return result;
    }
    return {fw: findUrls(fw, 'fw.', 0), idx: findUrls(idx, 'idx.', 0)};
})()""")
print(json.dumps(fw_state, ensure_ascii=False, indent=2))

# Look for click handler on "企业开办"
print("\n=== '企业开办' element details ===")
ent_elements = ev("""(function(){
    var results = [];
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
    while (walker.nextNode()) {
        var el = walker.currentNode;
        var text = el.textContent.trim();
        if (text === '企业开办' && el.childElementCount === 0) {
            var r = el.getBoundingClientRect();
            var parent = el.parentElement;
            var pp = parent ? parent.parentElement : null;
            results.push({
                tag: el.tagName,
                text: text,
                x: r.x, y: r.y, w: r.width, h: r.height,
                parentTag: parent ? parent.tagName : '',
                parentClass: parent ? parent.className : '',
                parentClick: parent ? !!parent.onclick : false,
                ppTag: pp ? pp.tagName : '',
                ppClass: pp ? pp.className : '',
                ppHref: pp ? (pp.href || '') : '',
                attrs: el.getAttributeNames().join(','),
            });
        }
    }
    return results;
})()""")
for e in (ent_elements or []):
    print(f"  '{e['text']}' @ ({e['x']:.0f},{e['y']:.0f}) {e['w']:.0f}x{e['h']:.0f}")
    print(f"    parent: {e['parentTag']}.{e['parentClass'][:40]} click={e['parentClick']}")
    print(f"    grandparent: {e['ppTag']}.{e['ppClass'][:40]} href={e['ppHref'][:60]}")

ws.close()
