"""Installed Edge + actual local API/TLS device check using the existing synthetic lab.

Requires the private Phase 6 pairing setup; never prints credentials or opens real
recordings. Approves a new synthetic device through the real manager UI and runs
the existing CPU model locally. It does not change operational table states.
"""

import json
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from uuid import uuid4

from verify_phase3_browser import click, end_session, open_browser

ROOT = Path(__file__).resolve().parents[1]


def main():
    setup = json.loads((ROOT/'.secrets/phase6/demo-setup.json').read_text(encoding='utf-8'))
    seed = json.loads((ROOT/'.secrets/phase2-demo-credentials.json').read_text(encoding='utf-8'))
    source, profile = setup['source'], setup['profile']
    letter = next(key for key,value in seed['organizations'].items() if value['id']==source['organization_id'])
    folder = ROOT/'.cache'/('phase6-browser-'+uuid4().hex)
    checks = []
    process = None
    with ExitStack() as stack:
        owner = stack.enter_context(open_browser(folder/'owner'))
        owner.send('Page.navigate',{'url':'http://localhost:3000/settings'})
        owner.login(seed['accounts'][letter+'_owner'])
        stack.callback(end_session,owner)
        loc = source['location_id']
        owner.evaluate(f"document.querySelectorAll('.switcher select')[0].value={json.dumps(source['organization_id'])};document.querySelectorAll('.switcher select')[0].dispatchEvent(new Event('change',{{bubbles:true}}))")
        owner.wait(f"Array.from(document.querySelectorAll('.switcher select')[1].options).some(o=>o.value==={json.dumps(loc)})")
        owner.evaluate(f"document.querySelectorAll('.switcher select')[1].value={json.dumps(loc)};document.querySelectorAll('.switcher select')[1].dispatchEvent(new Event('change',{{bubbles:true}}))")
        owner.wait("!!document.querySelector('[aria-labelledby=devices-title] input[name=request_id]')")
        devices = owner.evaluate(f"fetch('/api/v1/locations/{loc}/devices').then(r=>r.json())")
        existing = [row for row in devices['keys'] if row['fingerprint']==setup['public_identity']['fingerprint']]
        if not existing:
            owner.fill('[aria-labelledby=devices-title] input[name=request_id]',setup['pairing']['request_id'])
            owner.fill('[aria-labelledby=devices-title] input[name=fingerprint]',setup['public_identity']['fingerprint'])
            owner.evaluate("document.querySelector('[aria-labelledby=devices-title] input[name=label]').value='Phase 6 synthetic device';document.querySelector('[aria-labelledby=devices-title] input[type=checkbox]').click()")
            click(owner,'Approve fingerprint',"document.querySelector('[aria-labelledby=devices-title]')")
            owner.wait("!!document.querySelector('.device-fingerprint')")
            devices = owner.evaluate(f"fetch('/api/v1/locations/{loc}/devices').then(r=>r.json())")
        key = next(row for row in devices['keys'] if row['fingerprint']==setup['public_identity']['fingerprint'])
        device = key['device_id']
        checks.append('Real manager UI approval/public fingerprint confirmed (existing approval is preserved on rerun)')
        region = profile['config']['regions'][0]
        owner.wait("!!document.querySelector('[aria-labelledby=devices-title] input[name=profile_sha256]')")
        owner.evaluate(f"document.querySelector('[aria-labelledby=devices-title] select[name=zone]').value={json.dumps(region['zone_id'])}")
        bound = [row for row in devices['bindings'] if row['device_id']==device and row['table_id']==region['table_id'] and row['enabled']]
        if not bound:
            owner.fill('[aria-labelledby=devices-title] input[name=profile_sha256]',profile['fingerprint'])
            owner.fill('[aria-labelledby=devices-title] input[name=model_sha256]',setup['model_sha256'])
            owner.evaluate("document.querySelector('[aria-labelledby=devices-title] input[name=profile_sha256]').form.querySelector('input[type=checkbox]').click()")
            click(owner,'Save camera binding',"document.querySelector('[aria-labelledby=devices-title]')")
            owner.wait(f"fetch('/api/v1/locations/{loc}/devices').then(r=>r.json()).then(v=>v.devices.some(d=>d.id==={json.dumps(device)}&&d.revision>=2))")
        if not next(row for row in devices['devices'] if row['id']==device)['processing_enabled']:
            click(owner,'Enable synthetic background processing',"document.querySelector('[aria-labelledby=devices-title]')")
        owner.wait(f"fetch('/api/v1/locations/{loc}/devices').then(r=>r.json()).then(v=>v.devices.some(d=>d.id==={json.dumps(device)}&&d.processing_enabled))")
        checks.append('Explicit synthetic camera/model/profile binding and separate processing approval')
        log = stack.enter_context((ROOT/'.secrets/phase6/browser-runner.log').open('w',encoding='utf-8'))
        process = subprocess.Popen([sys.executable,'-m','restaurant_edge.cli','device-run','--settings',
            str(ROOT/'.secrets/phase6/runner.json'),'--seconds','22'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            owner.send('Page.navigate',{'url':f'http://localhost:3000/dashboard?location={loc}'})
            owner.wait("document.body.innerText.includes('Updates connected')")
            deadline = time.monotonic()+35  # Health cadence is 15 seconds, longer than Browser.wait's 12s.
            while not owner.evaluate(f"document.querySelector('[data-device-id=\"{device}\"]')?.innerText.includes('Inference: RUNNING')"):
                if time.monotonic()>deadline:
                    raise RuntimeError('Live device inference health did not arrive within its bounded window')
                time.sleep(.2)
            assert owner.evaluate("document.querySelector('[aria-label=\"Edge device health\"]').innerText.includes('shadow information')")
            checks.append('Real HTTPS heartbeat reached the live dashboard via authorized SSE; CPU inference RUNNING')
            owner.send('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            assert owner.evaluate('document.documentElement.scrollWidth<=window.innerWidth+2')
            checks.append('390-pixel mobile dashboard fits without horizontal overflow')
            assert process.wait(timeout=30) == 0
            owner.wait(f"document.querySelector('[data-device-id=\"{device}\"]')?.innerText.includes('Inference: STOPPED')")
            checks.append('Clean runner shutdown publishes degraded/stopped health while the dashboard remains usable')
            other = 'b' if letter=='a' else 'a'
            other_loc = seed['organizations'][other]['locations'][0]
            assert owner.evaluate(f"fetch('/api/v1/locations/{other_loc}/devices').then(r=>r.status)") == 404
            assert owner.evaluate("fetch('/api/v1/edge/heartbeat',{method:'POST',body:'{}'}).then(r=>r.status)") == 404
            checks.append('Cross-restaurant device read denied; browser proxy refuses machine endpoints')
            assert owner.errors == 0
        finally:
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
    result = {'passed':len(checks),'checks':checks,'synthetic_only':True,'real_person_accuracy_verified':False}
    (ROOT/'.secrets/phase6-implementation/browser-results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
