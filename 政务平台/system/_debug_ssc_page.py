"""Debug ssc page: check reachability, content, and what it's trying to do."""
import json, time, requests, websocket, urllib3
urllib3.disable_warnings()

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

# Check current page
href = ev("location.href") or ""
print(f"Current URL: {href}")

# If not on ssc, navigate there
if "ssc.mohrss" not in href:
    print("Not on ssc page. Checking browser console for errors...")
else:
    print("\n=== ssc page analysis ===")
    
    # Get page title
    title = ev("document.title")
    print(f"Title: {title}")
    
    # Get body text
    body = ev("document.body ? document.body.innerText.substring(0, 1000) : 'no body'")
    print(f"Body text: {body[:500] if body else 'empty'}")
    
    # Get all scripts
    scripts = ev("""(function(){
        var scripts = document.querySelectorAll('script');
        var result = [];
        for(var i=0;i<scripts.length;i++){
            var s = scripts[i];
            result.push({
                src: s.src || '',
                inline: s.src ? '' : s.textContent.substring(0, 200)
            });
        }
        return result;
    })()""")
    print(f"\nScripts ({len(scripts or [])}):")
    for s in (scripts or []):
        if s.get('src'):
            print(f"  src: {s['src'][:100]}")
        elif s.get('inline'):
            print(f"  inline: {s['inline'][:150]}")
    
    # Get all links/redirects
    meta = ev("document.querySelector('meta[http-equiv=\"refresh\"]') ? document.querySelector('meta[http-equiv=\"refresh\"]').content : 'none'")
    print(f"\nMeta refresh: {meta}")
    
    # Check for iframes
    iframes = ev("document.querySelectorAll('iframe').length")
    print(f"Iframes: {iframes}")
    
    # Check for forms
    forms = ev("""(function(){
        var forms = document.querySelectorAll('form');
        var result = [];
        for(var i=0;i<forms.length;i++){
            result.push({
                action: forms[i].action || '',
                method: forms[i].method || '',
                inputs: forms[i].querySelectorAll('input').length
            });
        }
        return result;
    })()""")
    print(f"Forms: {json.dumps(forms, ensure_ascii=False)}")
    
    # Check window.location and any pending redirects
    pending_redirect = ev("""(function(){
        // Check if there's a setTimeout or similar
        var result = {};
        result.href = location.href;
        result.readyState = document.readyState;
        // Check for common redirect patterns in the HTML
        var html = document.documentElement.outerHTML;
        if (html.indexOf('location.href') > -1) result.hasLocationHref = true;
        if (html.indexOf('location.replace') > -1) result.hasLocationReplace = true;
        if (html.indexOf('window.open') > -1) result.hasWindowOpen = true;
        if (html.indexOf('submit') > -1) result.hasSubmit = true;
        if (html.indexOf('redirect') > -1) result.hasRedirect = true;
        if (html.indexOf('callback') > -1) result.hasCallback = true;
        return result;
    })()""")
    print(f"\nPage analysis: {json.dumps(pending_redirect, ensure_ascii=False)}")
    
    # Get full HTML (first 3000 chars)
    html = ev("document.documentElement.outerHTML.substring(0, 3000)")
    print(f"\nHTML (first 3000):\n{html}")

# Test ssc reachability from Python
print("\n\n=== Python requests test ===")
try:
    r = requests.get("https://ssc.mohrss.gov.cn/pc/code/index.html?dataToken=TEST", 
                      verify=False, timeout=10)
    print(f"Status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('Content-Type','')}")
    print(f"Body (first 500): {r.text[:500]}")
except Exception as e:
    print(f"ERROR: {e}")

# Also test the ssc API endpoint
try:
    r2 = requests.get("https://ssc.mohrss.gov.cn/", verify=False, timeout=10)
    print(f"\nssc.mohrss.gov.cn root: {r2.status_code}")
except Exception as e:
    print(f"ssc root ERROR: {e}")

ws.close()
