"""Real browser-code session check using stdlib only; credentials stay in private config."""
import http.cookiejar,json,os,ssl,urllib.request,urllib.parse,urllib.error
from html.parser import HTMLParser
from pathlib import Path
class Forms(HTMLParser):
    def __init__(self,text):
        super().__init__();self.forms=[];self.current=None;self.feed(text)
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='form':self.current={'action':a.get('action',''),'fields':{}};self.forms.append(self.current)
        elif tag=='input' and self.current is not None and a.get('name'):self.current['fields'][a['name']]=a.get('value','')
    def handle_endtag(self,tag):
        if tag=='form':self.current=None
ctx=ssl.create_default_context(cafile=os.environ['KC_CA_FILE'])
jar=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=ctx),urllib.request.HTTPCookieProcessor(jar))
base=os.environ['KC_RAZOR_REDIRECT_URI'].removesuffix('/signin-oidc');identity=json.loads(Path('/config/validation.json').read_text())
def get(path):return client.open(base+path,timeout=40)
def post(url,values):return client.open(url,data=urllib.parse.urlencode(values).encode(),timeout=40)
with get('/Cuenta/Acceder') as r:page=r.read().decode();url=r.url
form=Forms(page).forms[0];form['fields'].update(username=identity['username'],password=identity['password'])
with post(urllib.parse.urljoin(url,form['action']),form['fields']) as r:page=r.read().decode();url=r.url
forms=Forms(page).forms
assert not any('otp' in f['fields'] or 'totp' in f['fields'] for f in forms),'Unexpected OTP'
if forms and 'code' in forms[0]['fields']:
    with post(urllib.parse.urljoin(url,forms[0]['action']),forms[0]['fields']) as r:page=r.read().decode();url=r.url
assert url.startswith(base+'/') and any(c.name=='platform-session' and c.secure for c in jar),'OIDC login failed'
print('PASS real username/password Code+PKCE session; no MFA')
for path in ['/Desastres','/Danos?disasterId='+str(identity['disasterId']),'/Reconstruccion?disasterId='+str(identity['disasterId'])]:
    with get(path) as r:assert r.status==200
    print('PASS portal',path)
with get('/Desastres') as r:page=r.read().decode()
form=next(f for f in Forms(page).forms if 'Cuenta/Salir' in f['action'])
try:post(base+'/Cuenta/Salir',{})
except urllib.error.HTTPError as error:assert error.code==400
else:raise AssertionError('Missing CSRF check')
with post(base+'/Cuenta/Salir',form['fields']) as r:assert r.status==200 and r.url.endswith('/Cuenta/Desconectado')
assert not any(c.name=='platform-session' for c in jar)
print('PASS CSRF and full logout')
