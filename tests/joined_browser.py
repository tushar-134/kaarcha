"""Joined real-backend browser tests. Starts/stops loopback-only services."""
import sys, tempfile, subprocess, time, json, urllib.request, pathlib, os
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'proof'; OUT.mkdir(exist_ok=True)
checks=[]
def check(name, condition):
    assert condition, name
    checks.append(name); print('PASS:',name,flush=True)
def get(path):
    return json.load(urllib.request.urlopen('http://127.0.0.1:5000/api/v1'+path))
def wait_server(url):
    for _ in range(60):
        try: urllib.request.urlopen(url);return
        except Exception:time.sleep(.1)
    raise RuntimeError('server failed')
with tempfile.TemporaryDirectory() as tmp:
  backend=subprocess.Popen([sys.executable,'run.py','--db',tmp+'/test.db'],cwd=ROOT,stdout=open(tmp+'/backend.log','w'),stderr=subprocess.STDOUT)

  try:
    wait_server('http://127.0.0.1:5000/api/v1/health');wait_server('http://127.0.0.1:5000')
    with sync_playwright() as p:
      browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
      page=browser.new_page(viewport={'width':1280,'height':1100})
      errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
      page.goto('http://127.0.0.1:5000/?demo');page.wait_for_function("document.querySelector('#exp-count').textContent === '4'")
      page.wait_for_function("document.querySelector('#backend-badge').textContent === 'Live'")
      check('Real API connected',page.locator('#backend-badge').text_content()=='Live')
      check('Expected seed names', [m['name'] for m in get('/members')['members']]==['Tushar','Nigamananda'])
      check('Whole-rupee currency has two decimals',page.locator('.balance-amount').first.text_content()=='−₹155.00')
      check('Seed balance 155 rupees', [b['net_paise'] for b in get('/balances')['balances']]==[-15500,15500])
      page.screenshot(path=str(OUT/'desktop.png'),full_page=True)
      # Add odd paise through actual form
      page.fill('#f-desc','Odd paise chai');page.fill('#f-amount','1.01');page.click('#add-btn')
      page.wait_for_function("document.querySelector('#exp-count').textContent === '5'")
      exp=get('/expenses')['expenses'][0]
      check('Equal split rounds first member up', sorted(s['amount_paise'] for s in exp['shares'])==[50,51])
      check('Saved paise amount via UI',exp['amount_paise']==101)
      check('Fractional share has two decimals','₹0.50' in page.locator('.expense-item').first.text_content())
      page.reload();page.wait_for_function("document.querySelector('#exp-count').textContent === '5'")
      check('SQLite survives browser reload',len(get('/expenses')['expenses'])==5)
      # Custom bad total blocked in UI
      page.fill('#f-desc','Custom lunch');page.fill('#f-amount','10');page.click('[data-mode=custom]')
      inputs=page.locator('#custom-inputs input');inputs.nth(0).fill('2');inputs.nth(1).fill('3');page.click('#add-btn')
      check('Invalid custom total visible',page.locator('#form-error').is_visible())
      check('Invalid custom total not saved',len(get('/expenses')['expenses'])==5)
      page.screenshot(path=str(OUT/'custom-error.png'),full_page=True)
      inputs.nth(1).fill('8');page.click('#add-btn');page.wait_for_function("document.querySelector('#exp-count').textContent === '6'")
      check('Exact custom split saved', sorted(s['amount_paise'] for s in get('/expenses')['expenses'][0]['shares'])==[200,800])
      # Actual server error propagated, no local save
      server_err=page.evaluate("""async () => {try {await KharchaAPI.addExpense({description:'bad',amount_paise:0,paid_by:1});return false;}catch(e){return e.code==='invalid_input';}}""")
      check('API 400 thrown, never fake saved',server_err and len(get('/expenses')['expenses'])==6)
      page.reload();page.wait_for_function("document.querySelector('#backend-badge').textContent === 'Live'")
      # Delete actual entry with confirmation
      page.once('dialog',lambda d:d.accept());page.locator('.exp-del').first.click()
      page.wait_for_function("document.querySelector('#exp-count').textContent === '5'")
      check('Delete persists',len(get('/expenses')['expenses'])==5)
      # Phone viewport screenshot + no horizontal overflow
      page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
      check('390px no horizontal overflow',page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
      page.set_viewport_size({'width':320,'height':740})
      check('320px no horizontal overflow',page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
      # reset cancel does not mutate, accept wipes only with honest confirmation
      dialogs=[]
      def reject(d): dialogs.append(d.message);d.dismiss()
      page.once('dialog',reject);page.click('#settle-btn')
      check('Reset warns deletion, not settlement', 'delete' in dialogs[0] and 'asli settlement nahi' in dialogs[0])
      check('Reset cancel keeps history',len(get('/expenses')['expenses'])==5)
      page.once('dialog',lambda d:d.accept());page.click('#settle-btn')
      page.wait_for_function("document.querySelector('#exp-count').textContent === '0'")
      check('Reset wipes expenses, recreates names',not get('/expenses')['expenses'] and len(get('/members')['members'])==2)
      # Test connectivity failure on save, preserve fields, no silent storage
      page.route('http://127.0.0.1:5000/api/**',lambda route:route.abort())
      page.fill('#f-desc','Cannot save offline');page.fill('#f-amount','20');page.click('#add-btn')
      page.wait_for_function("document.querySelector('#backend-badge').textContent === 'Offline'")
      check('Offline error preserves unsaved form',page.input_value('#f-desc')=='Cannot save offline' and page.locator('#form-error').is_visible())
      check('Offline previous balances labelled stale',page.locator('#connection-status').is_visible() and 'pichhli baar' in page.locator('#connection-status').text_content())
      check('No localStorage financial data',page.evaluate('localStorage.length')==0)
      page.screenshot(path=str(OUT/'offline-error.png'),full_page=True)
      fresh=browser.new_page(viewport={'width':390,'height':844})
      fresh.route('http://127.0.0.1:5000/api/**',lambda route:route.abort())
      fresh.goto('http://127.0.0.1:5000/')
      fresh.wait_for_function("document.querySelector('#backend-badge').textContent === 'Offline'")
      check('Initial offline never asserts unknown zero balances',not fresh.locator('#balance-card').is_visible() and not fresh.locator('#expense-section').is_visible() and fresh.locator('#connection-status').is_visible())
      fresh.screenshot(path=str(OUT/'offline-startup.png'),full_page=True)
      fresh.close()
      check('No JavaScript runtime errors',not errors)
      browser.close()
    # restart backend against same SQLite and read saved members
    backend.terminate();backend.wait()
    backend=subprocess.Popen([sys.executable,'run.py','--db',tmp+'/test.db'],cwd=ROOT,stdout=open(tmp+'/restart.log','w'),stderr=subprocess.STDOUT)
    wait_server('http://127.0.0.1:5000/api/v1/health')
    check('SQLite survives process restart',len(get('/members')['members'])==2)
  finally:
    backend.terminate(); backend.wait()
(OUT/'joined-tests.json').write_text(json.dumps({'passed':len(checks),'checks':checks},indent=2))
print('ALL',len(checks),'CHECKS PASSED')
