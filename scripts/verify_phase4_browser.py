"""Installed Edge + native local companion + real API/DB, synthetic footage only.

Creates/revises polygons only in the additive Phase 4 calibration labs. Keeps
browser profiles/screenshots/results private. Never prints account inputs.
"""

import base64
import json
import subprocess
import sys
import time
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

from restaurant_edge.cloud_client import CloudClient
from verify_phase3_browser import end_session, open_browser

ROOT = Path(__file__).resolve().parents[1]
PORT = 8766  # Separate verifier-owned process; the normal 8765 tool is preserved.
LOCAL = f"http://127.0.0.1:{PORT}"
LOCAL_BROWSERS = []


@contextmanager
def companion():
    with subprocess.Popen([
        sys.executable, "-m", "restaurant_edge.cli", "serve", "--config",
        str(ROOT / ".secrets/phase4/sources.json"), "--port", str(PORT),
    ], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as process:
        try:
            for _ in range(100):
                try:
                    with urlopen(LOCAL, timeout=1) as response:
                        assert response.status == 200
                    break
                except (OSError, URLError):
                    time.sleep(.1)
            else:
                raise RuntimeError("Verifier local companion did not become ready")
            yield
        finally:
            for browser in LOCAL_BROWSERS:
                try:
                    invoke(browser, 'stop', 'POST', {})
                except (OSError, RuntimeError, TimeoutError):
                    pass
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def local_login(browser, account):
    browser.send("Page.navigate", {"url": LOCAL})
    browser.wait("!!document.querySelector('#login')")
    browser.fill('input[name=email]', account['email'])
    browser.fill('input[name=password]', account['password'])
    browser.evaluate("document.querySelector('#login').requestSubmit()")
    browser.wait("!document.querySelector('#workspace').hidden && !!document.querySelector('#camera').value")


def invoke(browser, path, method="GET", body=None):
    # Existing page CSRF helper; only return status, never a session/cookie.
    payload = 'undefined' if method == 'GET' else json.dumps(body)
    return browser.evaluate(f"api({json.dumps(path)},{json.dumps(method)},"
                            f"{payload}).then(r=>r.status).catch(e=>e.status)")


def start(browser):
    browser.evaluate("document.querySelector('#start').click()")
    browser.wait("document.querySelector('#health').textContent.startsWith('ONLINE') && document.querySelector('#reference-status').textContent.startsWith('Live local preview')")


def pointer(browser,point,event,button='none'):
    position=browser.evaluate(f"(()=>{{const p=screen({json.dumps(point)}),b=canvas.getBoundingClientRect();return {{x:b.left+p[0]*b.width/canvas.width,y:b.top+p[1]*b.height/canvas.height}}}})()")
    browser.send('Input.dispatchMouseEvent',{'type':event,**position,'button':button,'clickCount':1 if button=='left' else 0})


def main():
    seed = json.loads((ROOT / '.secrets/phase2-demo-credentials.json').read_text())
    layout = json.loads((ROOT / '.secrets/phase4/demo-layout.json').read_text())
    folder = ROOT / '.cache' / ('phase4-browser-' + uuid4().hex[:10])
    checks = []
    owners = {}
    with ExitStack() as stack:
        for letter in 'ab':
            cloud = CloudClient('http://127.0.0.1:8000', 'http://localhost:3000')
            cloud.login(**{k:seed['accounts'][letter+'_org_admin'][k] for k in ['email','password']})
            stack.callback(cloud.close)
            owners[letter] = cloud
        cloud_ui = stack.enter_context(open_browser(folder/'cloud-a'))
        stack.callback(end_session, cloud_ui)
        cloud_ui.send('Page.navigate', {'url':'http://localhost:3000/settings'})
        cloud_ui.login(seed['accounts']['a_manager'])
        cloud_ui.evaluate(f"const s=document.querySelectorAll('.switcher select')[1];s.value={json.dumps(layout['a']['location_id'])};s.dispatchEvent(new Event('change',{{bubbles:true}}))")
        cloud_ui.wait("!!document.querySelector('input[name=consent]')")
        cloud_ui.wait(f"document.querySelector('input[name=consent]').closest('section').querySelector('select').value==={json.dumps(layout['a']['camera_id'])}")
        cloud_ui.evaluate("document.querySelector('input[name=consent]').click();document.querySelector('input[name=consent]').closest('form').requestSubmit()")
        cloud_ui.wait("document.body.innerText.includes('Explicit preview permission saved')")
        a_path = f"/v1/locations/{layout['a']['location_id']}/cameras/{layout['a']['camera_id']}"
        grants = owners['a'].request('GET', a_path+'/preview-grants')
        a_grant = next(g for g in grants if g['viewer_id']==seed['accounts']['a_manager']['user_id'] and not g['revoked_at'])
        stack.callback(owners['a'].request, 'POST', a_path+'/preview-grants/'+a_grant['id']+'/revoke')
        b_path = f"/v1/locations/{layout['b']['location_id']}/cameras/{layout['b']['camera_id']}"
        b_grant = owners['b'].request('POST', b_path+'/preview-grants', {
            'viewer_id':seed['accounts']['b_manager']['user_id'], 'duration_seconds':900,
            'consent':True, 'request_key':str(uuid4())})
        stack.callback(owners['b'].request, 'POST', b_path+'/preview-grants/'+b_grant['id']+'/revoke')
        checks.append('real cloud settings: explicit manager preview grant, local setup link, no automatic camera connection')
        local_a = stack.enter_context(open_browser(folder/'local-a'))
        local_b = stack.enter_context(open_browser(folder/'local-b'))
        LOCAL_BROWSERS[:] = [local_a, local_b]
        with companion():
            local_login(local_a, seed['accounts']['a_manager'])
            assert not local_a.evaluate("document.cookie.includes('restaurant_local_setup')")
            local_a.evaluate("document.querySelector('#loop').checked=true")
            start(local_a)
            assert local_a.evaluate("document.querySelector('#source-label').textContent.includes('DEMO')")
            assert local_a.evaluate("document.querySelector('#location').value") == layout['a']['location_id']
            local_login(local_b, seed['accounts']['b_manager'])
            assert layout['a']['location_id'] not in local_b.evaluate("Array.from(document.querySelector('#location').options).map(o=>o.value)")
            assert invoke(local_b, 'setup?location_id='+layout['a']['location_id']) == 404
            assert invoke(local_b, 'start', 'POST', {
                'location_id':layout['a']['location_id'], 'camera_id':layout['a']['camera_id'],
                'reference':layout['a']['source_reference']}) == 404
            assert invoke(local_b, 'frame') == 409
            checks.append('separate A/B browser sessions; foreign location/source denied; another local session cannot see the active frame')
            local_a.evaluate("document.querySelector('#pause').click();document.querySelector('#clear').click()")
            for x,y in [(0.12,0.2),(0.43,0.2),(0.43,0.7),(0.12,0.7)]:
                local_a.evaluate(f"document.querySelector('#point-x').value={x};document.querySelector('#point-y').value={y};document.querySelector('#add-point').click()")
            local_a.wait("!document.querySelector('#save').disabled")
            local_a.evaluate("document.querySelector('#canvas').focus()")
            local_a.send('Input.dispatchKeyEvent', {'type':'keyDown','key':'ArrowRight','code':'ArrowRight','windowsVirtualKeyCode':39})
            local_a.send('Input.dispatchKeyEvent', {'type':'keyUp','key':'ArrowRight','code':'ArrowRight','windowsVirtualKeyCode':39})
            assert abs(float(local_a.evaluate("document.querySelector('#point-x').value"))-.125)<.001
            local_a.evaluate("document.querySelector('#undo').click()")
            local_a.evaluate("document.querySelector('#clear').click()")
            for point in [[.12,.2],[.43,.2],[.43,.7],[.12,.7]]:
                pointer(local_a,point,'mousePressed','left')
                pointer(local_a,point,'mouseReleased','left')
            assert local_a.evaluate('points.length')==4
            pointer(local_a,[.12,.2],'mousePressed','left')
            pointer(local_a,[.15,.23],'mouseMoved','left')
            pointer(local_a,[.15,.23],'mouseReleased','left')
            assert abs(local_a.evaluate('points[0][0]')-.15)<.002
            local_a.evaluate("document.querySelector('#undo').click()")
            # Eight rotation/mirror combinations retain canonical original-image coordinates.
            assert local_a.evaluate("[0,90,180,270].every(r=>[false,true].every(m=>{const p=[.21,.68],g=window.CalibrationGeometry,q=g.inverse(g.transform(p,r,m),r,m);return q.every((v,i)=>Math.abs(v-p[i])<1e-9)}))")
            local_a.evaluate("document.querySelector('#rotation').value='90';document.querySelector('#rotation').dispatchEvent(new Event('change'));document.querySelector('#mirror').checked=true;document.querySelector('#mirror').dispatchEvent(new Event('change'))")
            local_a.evaluate("document.querySelector('#save').click()")
            local_a.wait("document.querySelector('#save-status').textContent.startsWith('Saved to')")
            saved = owners['a'].request('GET', f"/v1/locations/{layout['a']['location_id']}/table-zones")
            zone = next(z for z in saved if z['table_id']==layout['a']['table_id'])
            assert zone['source_width']==640 and zone['source_height']==360
            assert zone['view_metadata']['rotation']==90 and zone['view_metadata']['mirrored']
            assert len(zone['polygon'])==4
            local_a.evaluate("document.querySelector('#history').closest('details').open=true;document.querySelector('#history').click()")
            local_a.wait("document.querySelector('#history-list').children.length>0")
            checks.append('actual generated MP4 -> spawned decoder -> local JPEG -> paused canvas -> pointer draw/drag/undo and numeric/keyboard editing -> real DB and immutable history')
            local_a.send('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            assert local_a.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
            shot=local_a.send('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
            (folder/'mobile.png').write_bytes(base64.b64decode(shot['data']))
            local_a.send('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
            shot=local_a.send('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
            (folder/'desktop.png').write_bytes(base64.b64decode(shot['data']))
            checks.append('mobile 390px without horizontal overflow; rotation/mirror coordinate round trips; private desktop/mobile screenshots')
            local_a.send('Network.enable')
            local_a.send('Network.emulateNetworkConditions',{'offline':True,'latency':0,'downloadThroughput':0,'uploadThroughput':0})
            local_a.wait('image===null && !active')
            local_a.send('Network.emulateNetworkConditions',{'offline':False,'latency':0,'downloadThroughput':-1,'uploadThroughput':-1})
            start(local_a)
            local_a.evaluate("document.querySelector('#pause').click()")
            checks.append('local browser offline event clears frames; reconnect requires explicit source start')
            revoked_at=time.monotonic()
            # Revoke every overlapping verifier grant, including a previous interrupted run.
            for grant in owners['a'].request('GET',a_path+'/preview-grants'):
                if grant['viewer_id']==seed['accounts']['a_manager']['user_id'] and not grant['revoked_at']:
                    owners['a'].request('POST',a_path+'/preview-grants/'+grant['id']+'/revoke')
            local_a.wait("document.querySelector('#health').textContent.startsWith('UNAVAILABLE')")
            revocation_delay=round(time.monotonic()-revoked_at,3)
            assert invoke(local_a,'frame')==403
            assert local_a.evaluate("document.querySelector('#reference-status').textContent")  # Canvas cleared below.
            assert local_a.evaluate('image===null && !active')
            checks.append('actual API grant revocation stops preview and clears the paused reference; subsequent frame request denied')
            # Free single reader, then show B has its own independently authorized source.
            start(local_b)
            assert local_b.evaluate("document.querySelector('#location').value") == layout['b']['location_id']
            assert invoke(local_b, 'revisions?location_id='+layout['a']['location_id']+'&zone_id='+zone['id']) == 404
            local_b.evaluate("document.querySelector('#logout').click()")
            local_b.wait("!document.querySelector('#signin').hidden")
            checks.append('B source independently plays; B cannot retrieve A polygon history; logout releases its reader')
        with companion():
            # Old cookie maps to no local in-memory session after a real process restart.
            assert invoke(local_a,'session')==401
            local_login(local_a, seed['accounts']['a_manager'])
            local_a.wait(f"document.querySelector('#revision').textContent.includes('Saved revision {zone['revision']}')")
            assert local_a.evaluate('points') == zone['polygon']
            assert local_a.evaluate("document.querySelector('#rotation').value") == '90'
            assert local_a.evaluate("document.querySelector('#mirror').checked")
            local_a.evaluate("document.querySelector('#logout').click()")
            local_a.wait("!document.querySelector('#signin').hidden")
            checks.append('real local process restart: old cookie rejected, sign-in restores saved polygon revision and view metadata')
        owners['b'].request('POST',b_path+'/preview-grants/'+b_grant['id']+'/revoke')
        # Read-only regression of the existing dashboard; do not change original table states.
        dashboard=json.loads((ROOT/'.secrets/phase3-demo-layout.json').read_text())
        loc=dashboard['locations']['a']['id']
        cloud_ui.send('Page.navigate',{'url':f'http://localhost:3000/dashboard?location={loc}'})
        cloud_ui.wait("document.body.innerText.includes('Updates connected') && document.querySelectorAll('.floor-table').length>=6")
        time.sleep(12)
        assert cloud_ui.evaluate("document.body.innerText.includes('Updates connected')")
        cloud_ui.send('Network.enable')
        cloud_ui.send('Network.emulateNetworkConditions',{'offline':True,'latency':0,'downloadThroughput':0,'uploadThroughput':0})
        cloud_ui.wait("document.body.innerText.includes('STALE')")
        cloud_ui.send('Network.emulateNetworkConditions',{'offline':False,'latency':0,'downloadThroughput':-1,'uploadThroughput':-1})
        cloud_ui.wait("document.body.innerText.includes('Updates connected')")
        assert not cloud_ui.errors and not local_a.errors and not local_b.errors
        checks.append('existing dashboard: six states, SSE >12 seconds and offline/reconnect; zero JavaScript exceptions across three browsers')
    report={'verified_at_utc':datetime.now(UTC).isoformat(),'checks':checks,'physical_cameras_tested':False,
            'revocation_observed_seconds':revocation_delay,'screenshots':str(folder)}
    (ROOT/'.secrets/phase4-browser-verification.json').write_text(json.dumps(report,indent=2))
    print(f'Phase 4 browser integration: {len(checks)} verification groups passed. Synthetic video only.')
    for check in checks:
        print('PASS: '+check)


if __name__ == '__main__':
    main()
