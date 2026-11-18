"""Security-only requests to real Jakarta and YARP, without invoking native Eden workflows."""
import runpy,os,json,urllib.request,urllib.error,urllib.parse
from pathlib import Path
if os.environ.get('SECURITY_ISOLATED_TESTS')!='1':raise RuntimeError('Set SECURITY_ISOLATED_TESTS=1 only for an isolated test realm')
for url in [os.environ['KC_PUBLIC_URL'],*filter(None,os.environ.get('SECURITY_CONSUMER_URLS','').split(',')),*filter(None,[os.environ.get('SECURITY_DAMAGE_URL'),os.environ.get('SECURITY_DISASTERS_URL')])]:
 assert urllib.parse.urlsplit(url).hostname in ('localhost','127.0.0.1'), 'Local isolated services only'
c=runpy.run_path(str(Path(__file__).with_name('configure.py')))
request,put,root,admin,base=(c[k] for k in ['request','put','root','token','base'])
name='security-consumer-checks'
existing=request(root+'/clients?clientId='+name,token=admin)
if not existing:
 request(root+'/clients',{'clientId':name,'protocol':'openid-connect','enabled':True,'serviceAccountsEnabled':True,'publicClient':False,'standardFlowEnabled':False,'directAccessGrantsEnabled':False,'fullScopeAllowed':False,'protocolMappers':c['claims']+[c['mapper']('audience','oidc-audience-mapper',{'included.client.audience':'integration-service','access.token.claim':'true'})]},admin)
client=request(root+'/clients?clientId='+name,token=admin)[0]
user=request(root+'/clients/'+client['id']+'/service-account-user',token=admin)
put(root+'/users/'+user['id'],{'attributes':{'organization_id':['security-test-A'],'disaster_id':['1']}})
role=next(r for r in request(root+'/roles',token=admin) if r['name']=='people.read')
request(root+'/users/'+user['id']+'/role-mappings/realm',[role],admin);request(root+'/clients/'+client['id']+'/scope-mappings/realm',[role],admin)
secret=request(root+'/clients/'+client['id']+'/client-secret',token=admin)['value']
token=request('/realms/platform/protocol/openid-connect/token',{'grant_type':'client_credentials','client_id':name,'client_secret':secret},form=True)['access_token']
wrong=next(x for x in request(root+'/clients',token=admin) if x['clientId']=='integration-disasters');wrongSecret=request(root+'/clients/'+wrong['id']+'/client-secret',token=admin)['value']
wrongToken=request('/realms/platform/protocol/openid-connect/token',{'grant_type':'client_credentials','client_id':'integration-disasters','client_secret':wrongSecret},form=True)['access_token']
path=Path(os.environ['SECURITY_TEST_CLIENT_FILE']);path.write_text(json.dumps({'clientId':name,'clientSecret':secret,'token':token}));path.chmod(0o600)
def status(origin,path,token=None,method='GET'):
 headers={'Authorization':'Bearer '+token} if token else {}
 if method=='POST':headers['Content-Type']='application/json'
 try:
  with urllib.request.urlopen(urllib.request.Request(origin+path,headers=headers,method=method,data=b'{}' if method=='POST' else None),timeout=10) as response:return response.status
 except urllib.error.HTTPError as error:return error.code
for origin in filter(None,os.environ.get('SECURITY_CONSUMER_URLS','').split(',')):
 assert status(origin,'/api/personas-afectadas',token)==200,(origin,'valid')
 assert status(origin,'/api/personas-afectadas',wrongToken)==401,(origin,'audience')
 assert status(origin,'/api/personas-afectadas','invalid')==401,(origin,'signature')
 assert status(origin,'/api/personas-afectadas',token,'POST')==403,(origin,'role')
 assert status(origin,'/api/personas-afectadas?disasterId=2',token)==403,(origin,'disaster')
 assert status(origin,'/api/personas-afectadas/987654321',token)==404,(origin,'organization/resource')
 print('PASS JWT acceptance, wrong audience/signature, role, disaster and resource isolation:',origin)

def principal(name,audience,roleName,organization):
    existing=request(root+'/clients?clientId='+name,token=admin)
    if not existing:
        request(root+'/clients',{'clientId':name,'protocol':'openid-connect','enabled':True,'serviceAccountsEnabled':True,'publicClient':False,'standardFlowEnabled':False,'directAccessGrantsEnabled':False,'fullScopeAllowed':False,'protocolMappers':c['claims']+[c['mapper']('audience','oidc-audience-mapper',{'included.client.audience':audience,'access.token.claim':'true'})]},admin)
    client=request(root+'/clients?clientId='+name,token=admin)[0]
    account=request(root+'/clients/'+client['id']+'/service-account-user',token=admin)
    put(root+'/users/'+account['id'],{'attributes':{'organization_id':[organization],'disaster_id':['1']}})
    role=next(r for r in request(root+'/roles',token=admin) if r['name']==roleName)
    request(root+'/users/'+account['id']+'/role-mappings/realm',[role],admin);request(root+'/clients/'+client['id']+'/scope-mappings/realm',[role],admin)
    secret=request(root+'/clients/'+client['id']+'/client-secret',token=admin)['value']
    return request('/realms/platform/protocol/openid-connect/token',{'grant_type':'client_credentials','client_id':name,'client_secret':secret},form=True)['access_token']
if os.environ.get('SECURITY_DAMAGE_URL'):
    import uuid
    damage=os.environ['SECURITY_DAMAGE_URL']
    a=principal('security-damage-a','damage-assessment-api','damage.write','security-test-A')
    b=principal('security-damage-b','damage-assessment-api','damage.write','security-test-B')
    assert status(damage,'/api/evaluaciones/catalogos',a)==200
    assert status(damage,'/api/evaluaciones/catalogos',token)==401
    assert status(damage,'/api/evaluaciones?disasterId=2',a)==403
    assert status(damage,'/api/evaluaciones/catalogos/tipos-activo',a,'POST')==403
    body={'disasterId':None,'assetId':'security-'+str(uuid.uuid4()),'assetTypeId':'Bridge','damageCategoryId':'Severe','evaluatedAt':'2026-11-18T00:00:00Z','location':'Synthetic','latitude':4.7,'longitude':-74,'description':'Security isolation fixture','evidence':[],'budget':150000.00}
    req=urllib.request.Request(damage+'/api/evaluaciones',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+b,'Idempotency-Key':str(uuid.uuid4())})
    with urllib.request.urlopen(req,timeout=10) as response:
        assert response.status==201
        evaluation=json.load(response)
    eid=evaluation['evaluationId']
    assert status(damage,'/api/evaluaciones/'+eid,b)==200
    assert status(damage,'/api/evaluaciones/'+eid,a)==404
    print('PASS real Damage WAR JWT, role, disaster and cross-organization evaluation isolation')
if os.environ.get('SECURITY_DISASTERS_URL'):
    owner=os.environ['SECURITY_DISASTERS_URL']
    auth=principal('security-disasters-reader','disasters-api','reconstruction.read','security-test-A')
    assert status(owner,'/api/desastres/2/historial',auth)==403
    assert status(owner,'/api/desastres/2/historial',token)==401
    assert status(owner,'/api/desastres/2/historial',wrongToken)==403
    print('PASS real .NET owner Keycloak JWT audience, roles and disaster grants')
