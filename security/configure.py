"""Idempotent realm configuration through the supported Keycloak administration API."""
import json,os,ssl,urllib.request,urllib.parse,urllib.error

base=os.environ['KC_PUBLIC_URL'].rstrip('/')
if not base.startswith('https://'):raise ValueError('HTTPS required')
context=ssl.create_default_context(cafile=os.environ.get('KC_CA_FILE'))
def request(path,body=None,token=None,form=False):
    headers={}
    if token:headers['Authorization']='Bearer '+token
    if body is not None:
        body=urllib.parse.urlencode(body).encode() if form else json.dumps(body).encode()
        headers['Content-Type']='application/x-www-form-urlencoded' if form else 'application/json'
    with urllib.request.urlopen(urllib.request.Request(base+path,data=body,headers=headers),context=context,timeout=15) as response:
        return json.load(response) if response.status!=204 and response.headers.get('Content-Length')!='0' else None

token=request('/realms/master/protocol/openid-connect/token',{'client_id':'admin-cli','grant_type':'password','username':os.environ['KC_BOOTSTRAP_ADMIN_USERNAME'],'password':os.environ['KC_BOOTSTRAP_ADMIN_PASSWORD']},form=True)['access_token']
roles=['disasters.admin','disasters.integration','reconstruction.read','reconstruction.write','damage.read','damage.write','damage.admin','org.read','org.admin','people.read','people.write','coordination.read','coordination.write']
for name in ['monitoring','gis','hospital','administrative','financial']:roles.append('integration.'+name)
realm={'realm':'platform','enabled':True,'sslRequired':'all','registrationAllowed':False,'resetPasswordAllowed':True,'bruteForceProtected':True,'accessTokenLifespan':300,'revokeRefreshToken':True,'refreshTokenMaxReuse':0,'otpPolicyType':'totp','otpPolicyAlgorithm':'HmacSHA256','otpPolicyDigits':6,'otpPolicyPeriod':30,'requiredActions':[{'alias':'CONFIGURE_TOTP','name':'Configure OTP','providerId':'CONFIGURE_TOTP','enabled':True,'defaultAction':True,'priority':10}],'roles':{'realm':[{'name':r} for r in roles]}}
try:request('/admin/realms',realm,token)
except urllib.error.HTTPError as failure:
    if failure.code!=409:raise
root='/admin/realms/platform'
def mapper(name,protocol,config):return {'name':name,'protocol':'openid-connect','protocolMapper':protocol,'config':config}
claims=[mapper('organization','oidc-usermodel-attribute-mapper',{'user.attribute':'organization_id','claim.name':'organization_id','jsonType.label':'String','access.token.claim':'true','id.token.claim':'true'}),mapper('disasters','oidc-usermodel-attribute-mapper',{'user.attribute':'disaster_id','claim.name':'disaster_id','jsonType.label':'int','multivalued':'true','access.token.claim':'true'}),mapper('roles','oidc-usermodel-realm-role-mapper',{'claim.name':'role','jsonType.label':'String','multivalued':'true','access.token.claim':'true'})]
clients=[]
for name in ['disasters-api','reconstruction-api','damage-assessment-api','integration-service']:
    clients.append({'clientId':name,'protocol':'openid-connect','enabled':True,'bearerOnly':True,'fullScopeAllowed':False})
for name in ['razor-web','android']:
    redirect=os.environ['KC_RAZOR_REDIRECT_URI'] if name=='razor-web' else os.environ['KC_ANDROID_REDIRECT_URI']
    clients.append({'clientId':name,'protocol':'openid-connect','enabled':True,'publicClient':name=='android','standardFlowEnabled':True,'directAccessGrantsEnabled':False,'implicitFlowEnabled':False,'redirectUris':[redirect],'webOrigins':[],'fullScopeAllowed':False,'attributes':{'pkce.code.challenge.method':'S256'},'protocolMappers':claims})
if os.environ.get('KC_EDEN_REDIRECT_URI'):
    clients.append({'clientId':'eden','protocol':'openid-connect','enabled':True,'publicClient':False,'standardFlowEnabled':True,'directAccessGrantsEnabled':False,'implicitFlowEnabled':False,'fullScopeAllowed':False,'redirectUris':[os.environ['KC_EDEN_REDIRECT_URI']],'webOrigins':[],'attributes':{'pkce.code.challenge.method':'S256'},'protocolMappers':[claims[0]]})
for name,audience in [('assessment-disasters','disasters-api'),('integration-disasters','disasters-api'),('integration-disasters-read','disasters-api'),('reconstruction-damage','damage-assessment-api'),('reconstruction-disasters','disasters-api')]:
    clients.append({'clientId':name,'protocol':'openid-connect','enabled':True,'publicClient':False,'serviceAccountsEnabled':True,'standardFlowEnabled':False,'directAccessGrantsEnabled':False,'fullScopeAllowed':False,'protocolMappers':claims+[mapper('audience','oidc-audience-mapper',{'included.client.audience':audience,'access.token.claim':'true'})]})
existing={c['clientId']:c for c in request(root+'/clients',token=token)}
for client in clients:
    if client['clientId'] not in existing:request(root+'/clients',client,token)
# Claims used for authorization are administratively managed, never self-service attributes.
profile=request(root+'/users/profile',token=token)
profile['attributes']=[a for a in profile.get('attributes',[]) if a['name'] not in ('organization_id','disaster_id')]+[{'name':name,'permissions':{'view':['admin'],'edit':['admin']},'multivalued':name=='disaster_id'} for name in ['organization_id','disaster_id']]
profile['unmanagedAttributePolicy']='ADMIN_EDIT'
def put(path,body):
    req=urllib.request.Request(base+path,data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='PUT')
    with urllib.request.urlopen(req,context=context,timeout=15):pass
put(root+'/users/profile',profile)
realm_roles={r['name']:r for r in request(root+'/roles',token=token)}
existing={c['clientId']:c for c in request(root+'/clients',token=token)}
for name in ['razor-web','android']:
    request(root+'/clients/'+existing[name]['id']+'/scope-mappings/realm',[realm_roles[r] for r in roles],token)
scopes={s['name']:s for s in request(root+'/client-scopes',token=token)}
for audience in ['disasters-api','reconstruction-api','damage-assessment-api','integration-service']:
    if audience not in scopes:
        request(root+'/client-scopes',{'name':audience,'protocol':'openid-connect','attributes':{'include.in.token.scope':'true'},'protocolMappers':[mapper('audience','oidc-audience-mapper',{'included.client.audience':audience,'access.token.claim':'true'})]},token)
        scopes={s['name']:s for s in request(root+'/client-scopes',token=token)}
    for name in ['razor-web','android']:
        put(root+'/clients/'+existing[name]['id']+'/optional-client-scopes/'+scopes[audience]['id'],{})
put(root,{'sslRequired':'all','bruteForceProtected':True,'accessTokenLifespan':300,'revokeRefreshToken':True,'refreshTokenMaxReuse':0,'otpPolicyType':'totp','otpPolicyAlgorithm':'HmacSHA256','otpPolicyDigits':6,'otpPolicyPeriod':30,'eventsEnabled':True,'eventsExpiration':86400,'adminEventsEnabled':True,'adminEventsDetailsEnabled':False})
put(root+'/authentication/required-actions/CONFIGURE_TOTP',{'alias':'CONFIGURE_TOTP','name':'Configure OTP','providerId':'CONFIGURE_TOTP','enabled':True,'defaultAction':True,'priority':10})
print('Realm and clients provisioned. No roles or organization/disaster grants assigned automatically.')
