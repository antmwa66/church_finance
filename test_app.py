import urllib.request
import urllib.parse
import http.cookiejar

base = 'http://127.0.0.1:5000'

cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

login_data = urllib.parse.urlencode({
    'username': 'admin',
    'password': 'admin123'
}).encode()

req = urllib.request.Request(base + '/login', data=login_data)
with opener.open(req) as resp:
    print('login status:', resp.status)

for path in ['/dashboard', '/admin/dashboard']:
    try:
        with opener.open(base + path) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            print(f'{path} status: {resp.status}, sidebar: {"sidebar" in html}, tiles: {"actions-grid" in html}')
    except Exception as e:
        print(f'{path} error: {e}')
