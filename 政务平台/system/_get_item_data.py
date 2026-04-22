"""Get full data of '企业开办' item from collapse-service on 6087."""
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

# Navigate to 6087
href = ev("location.href")
if "6087" not in str(href):
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
    time.sleep(5)

# Get first '经营主体登记' section item details
result = ev("""(function(){
    var app = document.getElementById('app');
    var vm = app.__vue__;
    function findAll(v, name) {
        var results = [];
        if (v.$options.name === name || v.$options._componentTag === name) results.push(v);
        for (var i = 0; i < (v.$children || []).length; i++) {
            results = results.concat(findAll(v.$children[i], name));
        }
        return results;
    }
    var sections = findAll(vm, 'collapse-service');
    for (var s = 0; s < sections.length; s++) {
        var cs = sections[s];
        var title = cs.title || cs.$props.title || '';
        if (title !== '经营主体登记') continue;
        
        var data = cs.data || cs.$props.data || [];
        // Return first 3 items with ALL string fields
        return data.slice(0, 5).map(function(item) {
            var obj = {};
            for (var k in item) {
                if (typeof item[k] === 'string') obj[k] = item[k];
                else if (typeof item[k] === 'number') obj[k] = item[k];
            }
            return obj;
        });
    }
    return 'section not found';
})()""")

print("=== 经营主体登记 items ===")
if isinstance(result, list):
    for i, item in enumerate(result):
        print(f"\nItem {i}:")
        for k, v in item.items():
            print(f"  {k}: {str(v)[:100]}")
else:
    print(result)

# Also check what happens when clicking an item
print("\n=== Item click handler ===")
handler = ev("""(function(){
    var app = document.getElementById('app');
    var vm = app.__vue__;
    function findAll(v, name) {
        var results = [];
        if (v.$options.name === name || v.$options._componentTag === name) results.push(v);
        for (var i = 0; i < (v.$children || []).length; i++) {
            results = results.concat(findAll(v.$children[i], name));
        }
        return results;
    }
    var sections = findAll(vm, 'collapse-service');
    for (var s = 0; s < sections.length; s++) {
        var cs = sections[s];
        // Get methods
        var methods = Object.keys(cs.$options.methods || {});
        // Get event listeners
        var listeners = Object.keys(cs.$listeners || {});
        // Get the template click handlers by looking at the render function
        var renderStr = cs.$options.render ? cs.$options.render.toString().substring(0, 500) : '';
        return {
            componentName: cs.$options.name,
            methods: methods,
            listeners: listeners,
            renderSnippet: renderStr.substring(0, 300),
            hasItemClick: methods.indexOf('handleItemClick') >= 0 || methods.indexOf('clickItem') >= 0 || methods.indexOf('handleClick') >= 0,
            allMethods: methods.join(', '),
        };
    }
    return 'not found';
})()""")
print(json.dumps(handler, ensure_ascii=False, indent=2))

# Check the main-body component for navigation methods
print("\n=== main-body navigation methods ===")
mb_info = ev("""(function(){
    var app = document.getElementById('app');
    var vm = app.__vue__;
    function findAll(v, name) {
        var results = [];
        if (v.$options.name === name || v.$options._componentTag === name) results.push(v);
        for (var i = 0; i < (v.$children || []).length; i++) {
            results = results.concat(findAll(v.$children[i], name));
        }
        return results;
    }
    var mbs = findAll(vm, 'main-body');
    if (mbs.length === 0) return 'main-body not found';
    var mb = mbs[0];
    var methods = Object.keys(mb.$options.methods || {});
    // Check for jump/navigate methods
    var jumpMethods = methods.filter(function(m) {
        return /jump|nav|redirect|open|click|enter/i.test(m);
    });
    return {
        allMethods: methods.join(', '),
        jumpMethods: jumpMethods,
        // Try to get method source for jump-related methods
        jumpSrc: jumpMethods.map(function(m) {
            return {name: m, src: mb.$options.methods[m].toString().substring(0, 300)};
        }),
    };
})()""")
print(json.dumps(mb_info, ensure_ascii=False, indent=2))

ws.close()
