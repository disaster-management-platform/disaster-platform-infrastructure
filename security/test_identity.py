"""Real issuer, Client Credentials and browser OTP checks against an isolated realm."""
import runpy,os,json,time,ssl,urllib.request,urllib.parse,base64,secrets,hashlib,hmac,struct,re
from pathlib import Path
import requests
from bs4 import BeautifulSoup
c=runpy.run_path(str(Path(__file__).with_name('configure.py')))
request,put,root,admin,base,context=(c[k] for k in ['request','put','root','token','base','context'])
client=next(x for x in request(root+'/clients',token=admin) if x['clientId']=='integration-disasters')
user=request(root+'/clients/'+client['id']+'/service-account-user',token=admin)
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
name='mfa-'+secrets.token_hex(5);password=secrets.token_urlsafe(30)
request(root+'/users',{'username':name,'enabled':True,'email':name+'@example.invalid','emailVerified':True,'firstName':'Synthetic','lastName':'Security','credentials':[{'type':'password','value':password,'temporary':False}],'requiredActions':['CONFIGURE_TOTP']},admin)
uid=next(u['id'] for u in request(root+'/users?username='+name,token=admin) if u['username']==name)
s=requests.Session();s.verify=os.environ['KC_CA_FILE'];verifier=secrets.token_urlsafe(48);challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
params={'client_id':'android','redirect_uri':os.environ['KC_ANDROID_REDIRECT_URI'],'response_type':'code','scope':'openid','code_challenge':challenge,'code_challenge_method':'S256','state':secrets.token_urlsafe(20)}
r=s.get(base+'/realms/platform/protocol/openid-connect/auth',params=params,timeout=15)
def submit(response,values):
 soup=BeautifulSoup(response.text,'html.parser');form=soup.select_one('form');assert form is not None
 fields={i['name']:i.get('value','') for i in form.select('input[name]')};fields.update(values)
 return s.post(urllib.parse.urljoin(response.url,form['action']),data=fields,allow_redirects=False,timeout=15)
r=submit(r,{'username':name,'password':password})
while r.is_redirect:r=s.get(urllib.parse.urljoin(base,r.headers['Location']),timeout=15)
soup=BeautifulSoup(r.text,'html.parser');field=soup.select_one('input[name=totpSecret]');assert field is not None,'OTP enrollment required'
manual=soup.select_one('a[href*=manual]')
if soup.select_one('#kc-totp-secret-key') is None and manual:
 r=s.get(urllib.parse.urljoin(r.url,manual['href']),timeout=15);soup=BeautifulSoup(r.text,'html.parser')
seed=soup.select_one('#kc-totp-secret-key').get_text(strip=True);counter=struct.pack('>Q',int(time.time())//30);digest=hmac.new(base64.b32decode(seed.replace(' ','')+'='*((-len(seed.replace(' ','')))%8),casefold=True),counter,hashlib.sha256).digest();offset=digest[-1]&15;otp=str((struct.unpack('>I',digest[offset:offset+4])[0]&0x7fffffff)%1000000).zfill(6)
r=submit(r,{'totp':otp,'userLabel':'Synthetic authenticator'})
assert r.is_redirect,r.status_code
credentials=request(root+'/users/'+uid+'/credentials',token=admin);assert any(x['type']=='otp' for x in credentials)
print('PASS browser authentication and real TOTP enrollment')

import jwt
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
put(root+'/clients/'+client['id'],{'attributes':{'access.token.lifespan':'5'}})
try:
    short=access()['access_token'];time.sleep(6)
    try:jwt.decode(short,key,algorithms=['RS256'],audience='disasters-api',issuer=base+'/realms/platform')
    except jwt.ExpiredSignatureError:pass
    else:raise AssertionError('Expired token accepted')
finally:put(root+'/clients/'+client['id'],{'attributes':{}})
req=urllib.request.Request(base+root+'/users/'+uid,headers={'Authorization':'Bearer '+admin},method='DELETE')
with urllib.request.urlopen(req,context=context,timeout=15):pass
print('PASS signature, issuer, audience and expiration rejection; synthetic browser user removed')
