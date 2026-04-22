import requests, json, websocket

r = requests.get('http://127.0.0.1:9225/json', timeout=5)
targets = r.json()
for t in targets:
    if '9087' in str(t.get('url','')) and t.get('type') == 'page':
        ws = websocket.create_connection(t['webSocketDebuggerUrl'], timeout=10)
        
        # 1. 检查页面当前是否有 loading 状态
        js1 = """
        (function() {
          const loading = document.querySelector('.is-loading, .el-loading-mask, [class*="loading"]');
          const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('下一步'));
          return JSON.stringify({
            href: location.href,
            hasLoading: !!loading,
            btnDisabled: btn ? btn.disabled : 'no_btn',
            btnClassName: btn ? btn.className : 'no_btn',
            btnText: btn ? btn.textContent.trim() : 'no_btn'
          });
        })()
        """
        ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression':js1,'returnByValue':True}}))
        res1 = json.loads(ws.recv())
        print('PAGE STATE:', res1.get('result',{}).get('result',{}).get('value',''))
        
        # 2. 检查 Vue 路由状态
        js2 = """
        (function() {
          const app = document.querySelector('#app');
          if (!app) return 'no_app';
          const vm = app.__vue__ || app.__VUE__;
          if (!vm) return 'no_vue';
          
          const router = vm.$router || vm.$root?.$router;
          const route = vm.$route || vm.$root?.$route;
          
          return JSON.stringify({
            hasRouter: !!router,
            hasRoute: !!route,
            routePath: route ? route.path : 'no_route',
            routeName: route ? route.name : 'no_route',
            routeQuery: route ? JSON.stringify(route.query) : 'no_route',
            routeHash: location.hash
          });
        })()
        """
        ws.send(json.dumps({'id':2,'method':'Runtime.evaluate','params':{'expression':js2,'returnByValue':True}}))
        res2 = json.loads(ws.recv())
        print('ROUTER:', res2.get('result',{}).get('result',{}).get('value',''))
        
        # 3. 检查页面上的错误提示
        js3 = """
        (function() {
          const msgs = document.querySelectorAll('.el-message, .el-notification, [class*="error"], [class*="toast"]');
          return Array.from(msgs).slice(0, 5).map(el => ({
            className: el.className,
            text: el.textContent.trim().substring(0, 200)
          }));
        })()
        """
        ws.send(json.dumps({'id':3,'method':'Runtime.evaluate','params':{'expression':js3,'returnByValue':True}}))
        res3 = json.loads(ws.recv())
        val3 = res3.get('result',{}).get('result',{}).get('value',[])
        print('MESSAGES:', val3)
        
        # 4. 检查表单验证错误
        js4 = """
        (function() {
          const errors = document.querySelectorAll('.el-form-item__error, .is-error, [class*="error"]');
          return Array.from(errors).slice(0, 5).map(el => ({
            className: el.className,
            text: el.textContent.trim().substring(0, 100),
            parentText: el.parentElement ? el.parentElement.textContent.trim().substring(0, 50) : ''
          }));
        })()
        """
        ws.send(json.dumps({'id':4,'method':'Runtime.evaluate','params':{'expression':js4,'returnByValue':True}}))
        res4 = json.loads(ws.recv())
        val4 = res4.get('result',{}).get('result',{}).get('value',[])
        print('FORM ERRORS:', val4)
        
        ws.close()
        break
