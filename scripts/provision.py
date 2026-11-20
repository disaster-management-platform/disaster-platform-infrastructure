"""Non-destructive bootstrap; uses only Python's standard library in a pinned utility image."""
import json, os, pathlib, runpy, time, urllib.request, ssl
root=pathlib.Path('/config')
ctx=ssl.create_default_context(cafile=os.environ['KC_CA_FILE'])
for attempt in range(60):
    try:
        with urllib.request.urlopen(os.environ['KC_PUBLIC_URL']+'/realms/master/.well-known/openid-configuration',context=ctx,timeout=5): break
    except Exception:
        if attempt == 59: raise
        time.sleep(2)
ns=runpy.run_path('security/configure.py')
request,put,api,token=ns['request'],ns['put'],ns['root'],ns['token']
clients={c['clientId']:c for c in request(api+'/clients',token=token)}
def readenv(name):
    result={}
    for line in (root/'runtime'/f'{name}.env').read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            k,v=line.split('=',1);result[k]=v.strip().strip('"').strip("'")
    return result
bindings=[('razor-web','presentation','Security__ClientSecret'),('assessment-disasters','damage','DISASTERS_OAUTH_CLIENT_SECRET'),('integration-disasters-read','integration','DISASTERS_READ_OAUTH_CLIENT_SECRET'),('integration-disasters','integration','DISASTERS_REPORT_OAUTH_CLIENT_SECRET'),('reconstruction-damage','reconstruction','ExternalApis__DamageAssessments__OAuth__ClientSecret'),('reconstruction-disasters','reconstruction','ExternalApis__Disasters__OAuth__ClientSecret')]
# Supply the SAME authorized secrets for existing clients. New realms get the supplied secrets.
for client,name,key in bindings:
    secret=readenv(name).get(key)
    if not secret: raise ValueError('Missing authorized client secret: '+client)
    current=request(api+'/clients/'+clients[client]['id']+'/client-secret',token=token)['value']
    if current!=secret:
        # Explicit operator-managed runtime configuration is the source of deployment secrets.
        put(api+'/clients/'+clients[client]['id'],{'secret':secret})
# Human grants are never inferred. Optional service grants are explicitly authorized in config.
roles={r['name']:r for r in request(api+'/roles',token=token)}
for item in json.loads((root/'grants.json').read_text()):
    name=item['clientId']
    if name not in {'assessment-disasters','integration-disasters','integration-disasters-read','reconstruction-damage','reconstruction-disasters'}: raise ValueError('Unsupported service grant')
    user=request(api+'/clients/'+clients[name]['id']+'/service-account-user',token=token)
    attrs={**user.get('attributes',{}),'organization_id':[str(item['organization_id'])],'disaster_id':[str(x) for x in item['disaster_id']]}
    put(api+'/users/'+user['id'],{'attributes':attrs})
    approved=[roles[r] for r in item['roles']]
    request(api+'/users/'+user['id']+'/role-mappings/realm',approved,token)
    request(api+'/clients/'+clients[name]['id']+'/scope-mappings/realm',approved,token)
path=pathlib.Path('/var/razor');path.mkdir(exist_ok=True);os.chown(path,1654,1654);path.chmod(0o700)
print('Bootstrap complete; identities, existing grants and domain data preserved.')
