// Visual behavior and transfer checks for the actual extracted website package.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright');

const [folder, evidence] = process.argv.slice(2).map(p => path.resolve(p));
const local = file => pathToFileURL(path.join(folder, file)).href;
const report = {opened: local('site.html'), samples: []};

async function waitProgress(page, value) {
  await page.waitForFunction(p => Number(document.querySelector('[data-qr-blocks]')?.dataset.progress) === p, value);
}

async function installProbe(page) {
  await page.evaluate(() => {
    window.lastReveal = null;
    const stage = document.querySelector('.qr-blocks-stage');
    const host = stage.closest('[data-qr-blocks]');
    stage.addEventListener('dblclick', event => {
      const time = event.timeStamp;
      const clock = host.dataset.motionTime;
      const yaw = +host.dataset.yaw, pitch = +host.dataset.pitch;
      // Do not force canvas readback inside the gesture handler.
      requestAnimationFrame(() => {
        window.lastReveal = {firstFrameMs: +(performance.now()-time).toFixed(1),
          clock, firstClock:host.dataset.motionTime, yaw, pitch, firstYaw:+host.dataset.yaw,
          firstPitch:+host.dataset.pitch, progress:Number(host.dataset.progress)};
      });
    }, {capture:true});
  });
}

async function desktop(browser) {
  const context = await browser.newContext({viewport:{width:1440,height:900}, offline:true});
  try {
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    await page.goto(local('site.html'));
    const host = page.locator('[data-qr-studio][data-ready="true"]');
    const stage = host.locator('.qr-blocks-stage');
    await stage.waitFor();
    assert.equal(await page.locator('h1').count(), 1);
    assert.equal(await host.locator('[data-marker], [data-qr-part], [data-qr-hotspot]').count(), 0);
    assert.equal(await page.locator('body').evaluate(node => node.scrollWidth), 1440);
    const clock = () => host.getAttribute('data-motion-time').then(Number);
    await page.screenshot({path:path.join(evidence,'desktop.png')});
    const start = await clock();
    const period = await page.evaluate(() => JSON.parse(document.querySelector(
      '[data-qr-studio] script[type="application/json"]').textContent).studio.composition.camera[3]);
    for (const [index, fraction] of [.10,.33,.58,.82,1.02].entries()) {
      await page.waitForFunction(limit => +document.querySelector('[data-qr-studio]').dataset.motionTime>limit,
        start+period*fraction);
      await stage.screenshot({path:path.join(evidence,`loop-${index+1}.png`)});
    }
    report.loop = {period, start, observed:await clock()};
    const bounds = await stage.boundingBox();
    const view = async () => ({
      yaw:Number(await host.getAttribute('data-yaw')),
      pitch:Number(await host.getAttribute('data-pitch')),
      clock:await clock(),
    });
    const opening = await view();
    const cursor = () => stage.evaluate(node => getComputedStyle(node).cursor);
    await stage.click({position:{x:91,y:125}});
    await page.mouse.move(bounds.x+bounds.width*.16,bounds.y+bounds.height*.28);
    await page.mouse.down();
    await page.mouse.move(bounds.x+bounds.width*.37,bounds.y+bounds.height*.30,{steps:5});
    await page.waitForFunction(() => document.querySelector('[data-qr-studio]').hasAttribute('data-dragging'),
      null,{timeout:1800});
    const side = await view();
    assert(Math.abs(side.yaw-opening.yaw)>1 && Math.abs(side.pitch-opening.pitch)>.08);
    assert.equal(await cursor(),'grabbing');
    await stage.screenshot({path:path.join(evidence,'orbit-side.png')});
    assert.deepEqual(await view(),side,'The loop clock and the selected angle must hold during a drag');
    await page.mouse.move(bounds.x+bounds.width*.58,bounds.y+bounds.height*.28,{steps:5});
    await page.waitForFunction(yaw=>+document.querySelector('[data-qr-studio]').dataset.yaw>yaw+1,side.yaw);
    const rear = await view();
    assert(rear.yaw-opening.yaw>2.8);
    await stage.screenshot({path:path.join(evidence,'orbit-back.png')});
    await page.mouse.up();
    assert.equal(await cursor(),'grab');
    await page.waitForFunction(value=>+document.querySelector('[data-qr-studio]').dataset.motionTime>value+.04,rear.clock);
    assert.equal((await view()).yaw,rear.yaw);
    assert.equal(await host.getAttribute('data-progress'),'0');
    report.orbit = {opening,side,rear,resumed:await view(),dragDidNotReveal:true};
    await installProbe(page);
    for (const [index,ms] of [0,133,428,1021,181,605].entries()) {
      await page.waitForTimeout(ms);
      await stage.dblclick({position:{x:90,y:90}});
      await page.waitForFunction(() => window.lastReveal !== null);
      const entry = await page.evaluate(() => window.lastReveal);
      assert.equal(entry.clock,entry.firstClock);
      assert(Math.abs(Math.sin((entry.yaw-entry.firstYaw)/2))<1e-6);
      assert.equal(entry.pitch,entry.firstPitch);
      assert(entry.progress>0 && entry.progress<1, JSON.stringify(entry));
      assert(entry.firstFrameMs < 100, JSON.stringify(entry));
      report.samples.push(entry);
      if (index===0) await stage.screenshot({path:path.join(evidence,'gather.png')});
      await waitProgress(page,1);
      if (index===0) {
        await stage.screenshot({path:path.join(evidence,'desktop-scan.png')});
        await page.screenshot({path:path.join(evidence,'website-scan.png')});
      }
      await stage.dblclick({position:{x:90,y:90}});
      await waitProgress(page,0);
      const restored=await view();
      assert(Math.abs(Math.sin((restored.yaw-entry.yaw)/2))<1e-6);
      assert.equal(restored.pitch,entry.pitch);
      if (index===0) report.orbit.restored=restored;
      await page.evaluate(() => {window.lastReveal=null;});
    }
    assert.deepEqual(errors,[]);
  } finally { await context.close(); }
}

async function mobile(browser) {
  const context = await browser.newContext({viewport:{width:390,height:844}, isMobile:true, hasTouch:true, offline:true});
  try {
    const page = await context.newPage();
    await page.goto(local('site.html'));
    const stage=page.locator('.qr-blocks-stage');
    await stage.waitFor();
    assert.equal(await page.locator('body').evaluate(node=>node.scrollWidth),390);
    await page.screenshot({path:path.join(evidence,'mobile.png')});
    await stage.tap({position:{x:75,y:90}});
    assert.equal(await page.locator('[data-qr-studio]').getAttribute('data-progress'),'0');
    const point = await stage.boundingBox();
    const host = page.locator('[data-qr-studio]');
    const startYaw = Number(await host.getAttribute('data-yaw'));
    const client = await context.newCDPSession(page);
    const send = (type,touchPoints) => client.send('Input.dispatchTouchEvent',{type,touchPoints});
    const x=point.x+point.width*.23, y=point.y+point.height*.46;
    await send('touchStart',[{x,y}]);
    await send('touchMove',[{x:x+32,y:y+5}]);
    await send('touchMove',[{x:x+74,y:y+12}]);
    await send('touchEnd',[]);
    await page.waitForFunction(value=>+document.querySelector('[data-qr-studio]').dataset.yaw>value+.65,startYaw);
    assert.equal(await host.getAttribute('data-progress'),'0');
    const dragYaw = Number(await host.getAttribute('data-yaw'));
    await stage.screenshot({path:path.join(evidence,'touch-orbit.png')});
    await page.touchscreen.tap(point.x+100,point.y+95);
    await page.touchscreen.tap(point.x+100,point.y+95);
    await waitProgress(page,1);
    await stage.screenshot({path:path.join(evidence,'mobile-scan.png')});
    await page.goto(local('embed.html'));
    const button=page.locator('[data-qr-switch]');
    await button.tap();
    await waitProgress(page,1);
    await button.tap();
    await waitProgress(page,0);
    report.touch = {doubleTap:true, standaloneButton:true, startYaw, dragYaw};
  } finally { await context.close(); }
}

async function accessible(browser) {
  const context = await browser.newContext({reducedMotion:'reduce', offline:true});
  try {
    const page = await context.newPage();
    // Exercise the same standalone embed URL in an independent parent page.
    await page.goto(local('site.html'));
    await page.evaluate(() => {
      const iframe = document.createElement('iframe');
      iframe.src = 'embed.html';
      iframe.title = '扫码打开品牌网页';
      iframe.style='width:380px;height:590px';
      document.body.replaceChildren(iframe);
    });
    const host = page.frameLocator('iframe').locator('[data-qr-studio][data-ready="true"]');
    await host.waitFor();
    const initial = await host.getAttribute('data-motion-time');
    await page.waitForTimeout(300);
    assert.equal(await host.getAttribute('data-motion-time'),initial);
    const initialYaw = Number(await host.getAttribute('data-yaw'));
    await host.locator('.qr-blocks-stage').press('ArrowRight');
    const frame = page.frames().find(child => child.parentFrame());
    await frame.waitForFunction(value=>+document.querySelector('[data-qr-studio]').dataset.yaw>value+.2, initialYaw);
    const arrowYaw = Number(await host.getAttribute('data-yaw'));
    assert(arrowYaw > initialYaw+.20, 'ArrowRight must rotate the embedded stage');
    await host.locator('.qr-blocks-stage').press('Enter');
    assert.equal(await host.getAttribute('data-progress'),'1');
    await host.locator('.qr-blocks-stage').press('Space');
    assert.equal(await host.getAttribute('data-progress'),'0');
    report.iframe = {offline:true,reducedMotion:true,keyboard:true,initialYaw,arrowYaw};
  } finally { await context.close(); }
  const noScript = await browser.newContext({javaScriptEnabled:false,offline:true});
  try {
    const page = await noScript.newPage();
    await page.goto(local('embed.html'));
    const image = page.locator('.qr-blocks-backup img');
    assert(await image.isVisible());
    assert(await image.evaluate(node=>node.complete && node.naturalWidth>0));
    report.noScriptBackup = true;
  } finally { await noScript.close(); }
}

(async () => {
  await fs.mkdir(evidence,{recursive:true});
  const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless:true,args:['--use-angle=metal','--enable-webgl','--disable-background-timer-throttling']});
  try {
    await desktop(browser);
    await mobile(browser);
    await accessible(browser);
    await fs.writeFile(path.join(evidence,'browser.json'),JSON.stringify(report,null,2));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
