"""Readiness and public routing, using trusted TLS and no host development toolchain."""
import json,os,ssl,urllib.request,urllib.error
ctx=ssl.create_default_context(cafile=os.environ['KC_CA_FILE'])
checks=[('https://'+os.environ['KC_RAZOR_REDIRECT_URI'].split('/')[2]+'/health',200),
        (os.environ['KC_PUBLIC_URL']+'/realms/platform/.well-known/openid-configuration',200),
        ('http://disasters:8080/api/tipos-desastre',200),
        ('http://damage:8080/api/evaluaciones/diagnostico/ready',200),
        ('http://integration:8080/api/integracion/diagnostico/ready',200),
        ('http://reconstruction:8080/api/reconstruccion/ready',200),
        ('http://eden:8000/eden_default/default/index',200),
        ('https://'+os.environ['KC_RAZOR_REDIRECT_URI'].split('/')[2]+'/api/desastres',401)]
for url,status in checks:
    try:
        with urllib.request.urlopen(url,context=ctx,timeout=40) as r:
            actual=r.status
            if '/.well-known/' in url: assert json.load(r)['issuer']==os.environ['KC_PUBLIC_URL']+'/realms/platform'
    except urllib.error.HTTPError as e: actual=e.code
    assert actual==status,(url,actual,status)
    print('PASS',url,actual)
