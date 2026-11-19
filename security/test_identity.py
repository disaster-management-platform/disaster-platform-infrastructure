"""Real issuer, Client Credentials and password/PKCE checks against an isolated realm."""
import runpy,os,json,time,urllib.request,urllib.parse,urllib.error,base64,secrets,hashlib,sys
import jwt
from pathlib import Path
import requests
from bs4 import BeautifulSoup
if os.environ.get('SECURITY_ISOLATED_TESTS')!='1':raise RuntimeError('Set SECURITY_ISOLATED_TESTS=1 only for an isolated test realm')
assert urllib.parse.urlsplit(os.environ['KC_PUBLIC_URL']).hostname in ('localhost','127.0.0.1'), 'Local isolated identity only'
c=runpy.run_path(str(Path(__file__).with_name('configure.py')))
request,put,root,admin,base,context=(c[k] for k in ['request','put','root','token','base','context'])
if '--browser-only' not in sys.argv:
    client=next(x for x in request(root+'/clients',token=admin) if x['clientId']=='integration-disasters')
    user=request(root+'/clients/'+client['id']+'/service-account-user',token=admin)
    assert user.get('attributes',{}).get('organization_id') in (None,['security-test-A']), 'Refusing to overwrite a configured runtime identity'
    attributes_before=dict(client.get('attributes',{}))
    put(root+'/users/'+user['id'],{'attributes':{'organization_id':['security-test-A'],'disaster_id':['1']}})
    role=next(x for x in request(root+'/roles',token=admin) if x['name']=='disasters.integration')
    request(root+'/users/'+user['id']+'/role-mappings/realm',[role],admin)
    request(root+'/clients/'+client['id']+'/scope-mappings/realm',[role],admin)
    secret=request(root+'/clients/'+client['id']+'/client-secret',token=admin)['value']
    def access():return request('/realms/platform/protocol/openid-connect/token',{'grant_type':'client_credentials','client_id':client['clientId'],'client_secret':secret},form=True)
    one=access();two=access();claims=json.loads(base64.urlsafe_b64decode(one['access_token'].split('.')[1]+'=='))
    assert claims['iss']==base+'/realms/platform' and 'disasters-api' in claims['aud']
    assert claims['organization_id']=='security-test-A' and claims['disaster_id']==[1] and claims['role']==['disasters.integration']
    assert one['expires_in']<=300 and 'refresh_token' not in one
    assert two['access_token'] and two['expires_in']>0
    print('PASS real Client Credentials, scope, audience, administrative claims and repeated acquisition')
# A synthetic browser user is provisioned only by this test, with no business roles.
name='password-'+secrets.token_hex(5);password=secrets.token_urlsafe(30)
request(root+'/users',{'username':name,'enabled':True,'email':name+'@example.invalid','emailVerified':True,'firstName':'Synthetic','lastName':'Security','credentials':[{'type':'password','value':password,'temporary':False}]},admin)
uid=next(u['id'] for u in request(root+'/users?username='+name,token=admin) if u['username']==name)
s=requests.Session();s.verify=os.environ['KC_CA_FILE'];verifier=secrets.token_urlsafe(48);challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
params={'client_id':'android','redirect_uri':os.environ['KC_ANDROID_REDIRECT_URI'],'response_type':'code','scope':'openid','code_challenge':challenge,'code_challenge_method':'S256','state':secrets.token_urlsafe(20),'nonce':secrets.token_urlsafe(20)}
r=s.get(base+'/realms/platform/protocol/openid-connect/auth',params=params,timeout=15)
def submit(response,values):
 soup=BeautifulSoup(response.text,'html.parser');form=soup.select_one('form');assert form is not None
 fields={i['name']:i.get('value','') for i in form.select('input[name]')};fields.update(values)
 return s.post(urllib.parse.urljoin(response.url,form['action']),data=fields,allow_redirects=False,timeout=15)
r=submit(r,{'username':name,'password':password})
assert r.is_redirect, 'Password authentication must complete without OTP enrollment'
credentials=request(root+'/users/'+uid+'/credentials',token=admin)
assert not any(x['type']=='otp' for x in credentials)
assert 'CONFIGURE_TOTP' not in request(root+'/users/'+uid,token=admin).get('requiredActions',[])
location=urllib.parse.urlparse(r.headers['Location'])
query=urllib.parse.parse_qs(location.query)
assert query.get('state')==[params['state']] and query.get('code')
browser=request('/realms/platform/protocol/openid-connect/token',{'grant_type':'authorization_code','client_id':'android','code':query['code'][0],'redirect_uri':params['redirect_uri'],'code_verifier':verifier},form=True)
keys=request('/realms/platform/protocol/openid-connect/certs')['keys']
idKey=jwt.PyJWK.from_dict(next(k for k in keys if k['kid']==jwt.get_unverified_header(browser['id_token'])['kid'])).key
identity=jwt.decode(browser['id_token'],idKey,algorithms=['RS256'],audience='android',issuer=base+'/realms/platform')
assert identity['nonce']==params['nonce'] and identity['sub']==uid
renewed=request('/realms/platform/protocol/openid-connect/token',{'grant_type':'refresh_token','client_id':'android','refresh_token':browser['refresh_token']},form=True)
assert renewed['access_token'] and renewed['refresh_token']!=browser['refresh_token']
try:request('/realms/platform/protocol/openid-connect/token',{'grant_type':'refresh_token','client_id':'android','refresh_token':browser['refresh_token']},form=True)
except urllib.error.HTTPError as failure:assert failure.code==400
else:raise AssertionError('Reused refresh token accepted')
print('PASS password-only browser, Authorization Code/S256 PKCE, ID-token nonce/signature and refresh rotation/replay denial')

if '--browser-only' not in sys.argv:
    keys=request('/realms/platform/protocol/openid-connect/certs')['keys']
    key=jwt.PyJWK.from_dict(next(k for k in keys if k['kid']==jwt.get_unverified_header(one['access_token'])['kid'])).key
    jwt.decode(one['access_token'],key,algorithms=['RS256'],audience='disasters-api',issuer=base+'/realms/platform')
    for kwargs in [{'audience':'wrong','issuer':base+'/realms/platform'},{'audience':'disasters-api','issuer':'https://wrong.invalid'}]:
        try:jwt.decode(one['access_token'],key,algorithms=['RS256'],**kwargs)
        except jwt.InvalidTokenError:pass
        else:raise AssertionError('Invalid issuer/audience accepted')
    parts=one['access_token'].split('.');parts[2]=('A' if parts[2][0]!='A' else 'B')+parts[2][1:]
    try:jwt.decode('.'.join(parts),key,algorithms=['RS256'],audience='disasters-api',issuer=base+'/realms/platform')
    except jwt.InvalidSignatureError:pass
    else:raise AssertionError('Invalid signature accepted')
    put(root+'/clients/'+client['id'],{'attributes':{**attributes_before,'access.token.lifespan':'5'}})
    try:
        short=access()['access_token'];time.sleep(6)
        try:jwt.decode(short,key,algorithms=['RS256'],audience='disasters-api',issuer=base+'/realms/platform')
        except jwt.ExpiredSignatureError:pass
        else:raise AssertionError('Expired token accepted')
    finally:put(root+'/clients/'+client['id'],{'attributes':attributes_before})
req=urllib.request.Request(base+root+'/users/'+uid,headers={'Authorization':'Bearer '+admin},method='DELETE')
with urllib.request.urlopen(req,context=context,timeout=15):pass
print('Synthetic browser user removed')
