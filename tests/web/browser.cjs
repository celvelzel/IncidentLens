const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
(async()=>{
 const out=process.env.WP_C_BROWSER_OUT || 'results/ci/browser';
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true, ...(process.env.CHROMIUM_PATH ? {executablePath:process.env.CHROMIUM_PATH} : {})});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 // Only this local server may receive requests; replay responses come from fixtures.
 const base=process.env.REPLAY_BASE_URL || 'http://127.0.0.1:8766';
 await page.route('**/*',route=>{
   if(new URL(route.request().url()).origin===new URL(base).origin) return route.continue();
   return route.abort('blockedbyclient');
 });
 const errors=[], mutations=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(r.url().includes('/api/run')) mutations.push(r.url());});
 let fixture='mock-success';
 await page.route('**/api/replay',route=>route.fulfill({json:{trace:JSON.parse(fs.readFileSync(`tests/web/fixtures/${fixture}.json`,'utf8')),path:'results/offline-fixture/trace.json',recorded:true,report_md:'offline fixture report'}}));
 await page.goto((process.env.REPLAY_BASE_URL || 'http://127.0.0.1:8766') + '/#/run?path=fixture');
 await page.locator('#replay-position').waitFor();
 await page.getByRole('tab',{name:'根因报告'}).click();
 assert.match(await page.locator('#run-tab-panel').innerText(),/not recorded/);
 await page.locator('[data-step=next]').click();
 assert.match(await page.locator('#replay-position').innerText(),/^1 /);
 await page.locator('[data-step=first]').click();
 await page.locator('#replay-speed').selectOption('4');
 await page.locator('#replay-play').click();
 await page.waitForTimeout(650);
 assert.match(await page.locator('#replay-play').innerText(),/暂停/);
 await page.locator('#replay-play').click();
 await page.locator('[data-step=last]').click();
 assert.match(await page.locator('#run-tab-panel').innerText(),/backend_pool_config_regression/);
 await page.getByRole('tab',{name:/证据登记/}).click();
 await page.locator('[data-ev]').first().click();
 await page.locator('#drawer:not([hidden])').waitFor();
 assert.match(await page.locator('#drawer-body').innerText(),/已记录查询/);
 await page.locator('#drawer-close').click();
 await page.getByRole('tab',{name:/调查时间线/}).click();
 await page.screenshot({path:path.join(out,'desktop.png'),fullPage:false});
 await page.setViewportSize({width:390,height:844});
 await page.waitForTimeout(400);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
 assert.ok(await page.locator('.replay-controls button').evaluateAll(nodes=>nodes.every(e=>e.getBoundingClientRect().right<=window.innerWidth)));
 await page.screenshot({path:path.join(out,'mobile.png'),fullPage:false});
 for(const next of ['mock-missing','provider-failure']) {
   fixture=next; await page.reload(); await page.locator('#replay-position').waitFor();
   await page.locator('[data-step=last]').click();
   await page.getByRole('tab',{name:'根因报告'}).click();
   assert.ok((await page.locator('#run-tab-panel').innerText()).length>0);
 }
 assert.deepEqual(errors,[]); assert.deepEqual(mutations,[]);
 await browser.close();
 console.log('PASS desktop/mobile, playback, prefix report, inspector provenance, saved missing/failure, no runtime errors, no /api/run');
})().catch(e=>{console.error(e);process.exit(1)});





