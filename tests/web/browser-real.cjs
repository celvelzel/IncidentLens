/** Actual HTTP server acceptance. No route interception, provider, or /api/run. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/RickyMa/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs'), path=require('node:path'), assert=require('node:assert/strict');
(async()=>{
 const base=process.env.REPLAY_BASE_URL || 'http://127.0.0.1:8797';
 const tracePath=process.env.WP_C_REAL_TRACE || 'results/v16/wp-c-real-replay/t5/trace.json';
 const out=process.env.WP_C_BROWSER_OUT || 'results/v16/wp-c-real-replay/browser';
 fs.mkdirSync(out,{recursive:true});
 const trace=JSON.parse(fs.readFileSync(tracePath,'utf8')),events=trace.state.events;
 const {replayBookmarks}=await import('../../src/incident_lens/web/static/js/replay.js');
 const bookmarks=replayBookmarks(trace), reviews=events.filter(e=>e.event_type === 'REVIEW');
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH || 'C:/Users/RickyMa/AppData/Local/ms-playwright/chromium-1217/chrome-win64/chrome.exe'});
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce',colorScheme:'dark'});
 const errors=[],runs=[],responses=[],screenshots=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(r.url().includes('/api/run')) runs.push(r.url());});
 page.on('response',r=>{if(r.url().includes('/api/replay')) responses.push({url:r.url(),status:r.status()});});
 const shot=async name=>{await page.screenshot({path:path.join(out,name),fullPage:false});screenshots.push(name);};
 const seek=async n=>{await page.locator('#replay-jump').fill(String(n));await page.locator('#replay-jump').press('Enter');assert.match(await page.locator('#replay-position').innerText(),new RegExp(`^${n} /`));};
 const open=async p=>{await page.goto(`${base}/#/run?path=${encodeURIComponent(p)}&demo=1`);await page.locator('#replay-position').waitFor();};
 try {
 await open(tracePath);
 assert.match(await page.locator('.hero-kicker').first().innerText(),/REAL LLM/);
 assert.equal(await page.locator('[href*="/api/download"]').count(),0);
 assert.equal(await page.locator('.replay-role').count(),0);
 await page.getByRole('tab',{name:'根因报告',exact:true}).click();
 assert.match(await page.locator('#run-tab-panel').innerText(),/not recorded/);
 await page.locator('#replay-metadata').evaluate(e=>e.open=true);
 assert.match(await page.locator('#replay-metadata').innerText(),/SOURCE DRIFT/);
 assert.match(await page.locator('#replay-metadata').innerText(),new RegExp(trace.model_id));
 await page.locator('#replay-metadata').evaluate(e=>e.open=false);
 await page.locator('.replay-heading').scrollIntoViewIfNeeded();await shot('01-source-drift-dark.png');
 await page.locator('[data-step=next]').click();assert.match(await page.locator('#replay-position').innerText(),/^1 /);
 await page.locator('[data-step=prev]').click();assert.match(await page.locator('#replay-position').innerText(),/^0 /);
 await page.locator('#replay-speed').selectOption('4');await page.locator('#replay-play').click();
 await page.waitForTimeout(650);await page.locator('#replay-play').click();
 assert.ok(Number((await page.locator('#replay-position').innerText()).split(' /')[0])>0);
 for(const id of ['dispatch','config','insufficient','postgres_connection_exhaustion','gate','backend_resource_saturation','last-review']) {
   const b=bookmarks.find(b=>b.id === id);assert.ok(b?.position,`missing real chapter ${id}`);
   await page.locator(`[data-bookmark="${id}"]`).click();
   assert.match(await page.locator('#replay-position').innerText(),new RegExp(`^${b.position} /`));
   if(id === 'dispatch') {await page.locator('#replay-workflow [data-role=changes]').click();assert.match(await page.locator('.replay-role-detail').innerText(),/task_changes/);}
   if(id === 'insufficient') {
     assert.equal(await page.locator('#replay-reviews article').count(),1);
     assert.match(await page.locator('#replay-workflow [data-role=logs]').innerText(),/未调度/);
     assert.match(await page.locator('#replay-reviews').innerText(),/insufficient/);
     await page.locator('#replay-reviews details').first().evaluate(e=>e.open=true);
   }
   if(id === 'backend_resource_saturation') assert.match(await page.locator('#replay-history').innerText(),/REJECTED/);
   await page.locator('#replay-selection').scrollIntoViewIfNeeded();await shot(`chapter-${id}.png`);
 }
 await page.locator('#replay-category').evaluate(e=>e.closest('details').open=true);
 await page.locator('#replay-category').selectOption('review');
 assert.equal(await page.locator('#replay-events button').count(),reviews.length);
 await seek(events.length);
 assert.equal(await page.locator('#replay-reviews article').count(),reviews.length);
 assert.equal(await page.locator('[href*="kind=report"]').count(),1);
 await page.getByRole('tab',{name:'根因报告',exact:true}).click();
 assert.match(await page.locator('#run-tab-panel').innerText(),/backend_pool_config_regression/);
 assert.equal(await page.locator('.causal-chain li').count(),trace.state.report.causal_chain.length);
 const download=await page.request.get(`${base}/api/download?path=${encodeURIComponent(tracePath)}&kind=report`);
 assert.equal(download.status(),200);assert.match(await download.text(),/backend_pool_config_regression/);
 await page.locator('#run-tab-panel').scrollIntoViewIfNeeded();await shot('final-report-dark.png');
 await page.locator('#run-tab-panel [data-evidence-id]').first().click();
 await page.locator('#drawer:not([hidden])').waitFor();
 const drawer=await page.locator('#drawer-body').innerText();
 assert.match(drawer,/已记录查询/);assert.match(drawer,/报告引用/);assert.match(drawer,/首次来源 Agent/);assert.match(drawer,/public\//);
 await shot('evidence-provenance.png');
 await page.locator('#replay-seek').evaluate(e=>{e.value='0';e.dispatchEvent(new Event('input',{bubbles:true}));});
 assert.equal(await page.locator('#drawer').isHidden(),true);assert.equal(await page.locator('#drawer-body').innerText(),'');
 assert.equal(await page.locator('[href*="/api/download"]').count(),0);
 assert.equal(await page.locator('#replay-history article').count(),0);
 assert.equal(await page.locator('#replay-reviews article').count(),0);
 assert.match(await page.locator('#run-tab-panel').innerText(),/not recorded/);
 await seek(events.length);
 await page.locator('#theme-toggle').click();
 assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
 await page.locator('#run-tab-panel').scrollIntoViewIfNeeded();await shot('final-report-light.png');
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(250);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile horizontal overflow');
 await page.locator('.replay-heading').scrollIntoViewIfNeeded();await shot('mobile-light.png');
 await page.setViewportSize({width:844,height:390});await page.waitForTimeout(250);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'landscape horizontal overflow');
 await shot('landscape-light.png');
 await page.setViewportSize({width:1440,height:1000});
 await page.goto(`${base}/#/library`);await page.locator('#lib-search').fill(trace.state.incident_id);
 await page.locator('[data-demo-link]').first().click();await page.locator('#replay-position').waitFor();
 assert.equal(await page.locator('#replay-demo').isChecked(),true);
 // Existing saved Mock/missing/provider-failure fixtures go through the real server.
 for(const name of ['mock-success','mock-missing','provider-failure']) {
   const dest=`results/v16/wp-c-real-replay/fixtures/${name}`;fs.mkdirSync(dest,{recursive:true});
   fs.copyFileSync(`tests/web/fixtures/${name}.json`,`${dest}/trace.json`);
   await open(`${dest}/trace.json`);await page.locator('[data-step=last]').click();
   await page.getByRole('tab',{name:'根因报告',exact:true}).click();assert.ok((await page.locator('#run-tab-panel').innerText()).length>0);
   assert.match(await page.locator('.hero-kicker').first().innerText(),/MOCK/);
 }
 for(const name of ['missing','corrupt']) {
   const p=`results/v16/wp-c-real-replay/${name}/trace.json`;
   if(name === 'corrupt'){fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,'{');}
   await page.goto(`${base}/#/run?path=${encodeURIComponent(p)}`);
   await page.getByText('无法加载该痕迹',{exact:true}).waitFor();
 }
 assert.deepEqual(errors,[]);assert.deepEqual(runs,[]);
 const receipt={passed:true,server:base,trace_path:tracePath,run_id:trace.state.run_id,event_count:events.length,review_count:reviews.length,review_verdicts:reviews.map(e=>e.details.review.verdict),bookmarks,responses,page_errors:errors,api_run_requests:runs,screenshots,intercepted:false,viewports:['1440x1000','390x844','844x390'],reduced_motion:true};
 fs.writeFileSync(path.join(out,'receipt.json'),JSON.stringify(receipt,null,2));
 console.log(JSON.stringify(receipt,null,2));
 } catch(error) {await shot('failure.png');throw error;} finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
