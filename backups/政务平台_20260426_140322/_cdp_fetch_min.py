"""极简诊断：直接调 fetch 看有无响应。"""
import json, time, urllib.request, websocket

tab = next(t for t in json.loads(urllib.request.urlopen('http://127.0.0.1:9225/json').read())
           if t.get('type') == 'page' and 'core.html' in t.get('url', ''))
ws = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=15)


def c(m, p=None, i=1):
    ws.send(json.dumps({'id': i, 'method': m, 'params': p or {}}))
    ws.settimeout(5)
    deadline = time.time() + 5
    while time.time() < deadline:
        try: msg = json.loads(ws.recv())
        except: continue
        if msg.get('id') == i: return msg.get('result', {})
    return {'_err': 'to'}


def ev(e, i):
    r = c('Runtime.evaluate', {'expression': e, 'returnByValue': True}, i)
    return r.get('result', {}).get('value'), r.get('exceptionDetails')


c('Runtime.enable', i=1)
c('Page.enable', i=50)
# 激活 tab（前台）
r = c('Page.bringToFront', i=51)
print(f'bringToFront: {r}')

v, err = ev('window.__x__ = 42; window.__x__', 2)
print(f'T1 assign+read: {v}  err={err}')

v, err = ev('typeof fetch', 3)
print(f'T2 fetch type: {v}')

# 用 XMLHttpRequest 代替 fetch
v, err = ev("""
(function(){
    window.__xhr_status__ = 'init';
    try {
        var x = new XMLHttpRequest();
        x.open('GET', '/');
        x.onload = function(){ window.__xhr_status__ = 'loaded_' + x.status; };
        x.onerror = function(){ window.__xhr_status__ = 'error'; };
        x.ontimeout = function(){ window.__xhr_status__ = 'timeout'; };
        x.send();
        return 'xhr_sent';
    } catch(e) {
        return 'EXC: ' + String(e);
    }
})()
""", 4)
print(f'T4 xhr send: {v}')

time.sleep(3)
v, err = ev('window.__xhr_status__', 5)
print(f'T4 after 3s xhr status: {v}')

# 试 fetch with catch logging
v, err = ev("""
(function(){
    window.__fx__ = 'init';
    try {
        fetch('https://www.baidu.com').then(function(r){
            window.__fx__ = 'resp_' + r.status;
        }).catch(function(e){
            window.__fx__ = 'catch_' + String(e).slice(0, 100);
        });
        return 'fetch_sent';
    } catch(e) {
        return 'sync_exc: ' + String(e);
    }
})()
""", 6)
print(f'T5 fetch baidu send: {v}')

time.sleep(4)
v, err = ev('window.__fx__', 7)
print(f'T5 after 4s fx: {v}')

ws.close()
