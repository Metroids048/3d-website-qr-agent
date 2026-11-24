/* Capture and verify the actual component canvas through native browser input. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const { pathToFileURL } = require('node:url');

const launch = () => chromium.launch({
  executablePath: process.env.QR_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  args: ['--enable-unsafe-swiftshader', '--no-proxy-server'],
});

async function trace(page) {
  await page.addInitScript(() => {
    const record = window.renderAudit = { writes: [], maps: [], uploads: [], draws: [], shaders: [] };
    if (!navigator.gpu) return;
    const intercept = (className, name, observe) => {
      const prototype = window[className].prototype;
      const original = prototype[name];
      prototype[name] = function(...args) {
        observe(...args);
        return original.apply(this, args);
      };
    };
    intercept('GPUDevice', 'createBuffer', item =>
      record.maps.push([item.label, item.size, item.usage, Boolean(item.mappedAtCreation)]));
    intercept('GPUDevice', 'createShaderModule', item => record.shaders.push(item.code));
    intercept('GPUQueue', 'writeBuffer', buffer => record.writes.push(buffer.label));
    intercept('GPUQueue', 'copyExternalImageToTexture', (_, target) => record.uploads.push(target.texture.label));
    intercept('GPURenderPassEncoder', 'draw', (vertices, instances) => record.draws.push([vertices, instances]));
  });
}

const frame = page => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));

function assertFixed(audit, n) {
  const draw = [30, n*n];
  assert.ok(audit.shaders.length && audit.shaders.every(shader => !/uniforms\.progress|morphProgress/.test(shader)),
    'shader permits interaction-driven geometry or material changes');
  assert.deepEqual(audit.maps, [
    ['terrain-columns', n*n*32, 128, true], ['terrain-shape', 32, 64, true], ['terrain-camera', 32, 72, false],
  ]);
  assert.deepEqual(audit.uploads, ['terrain-material']);
  assert.ok(audit.writes.length >= 3 && audit.writes.every(label => label === 'terrain-camera'));
  assert.ok(audit.draws.length >= 3 && audit.draws.every(call => call[0] === draw[0] && call[1] === draw[1]));
  return { instances: draw[1], cameraWrites: audit.writes.length, materialUploads: audit.uploads.length };
}

async function drag(page, canvas, receive) {
  const box = await canvas.boundingBox();
  const x = box.x + box.width * .55;
  const y = box.y + box.height * .72;
  const angle = () => canvas.getAttribute('data-angle').then(Number);
  assert.equal(await angle(), 32);
  const samples = [{ distance:0, angle:32 }];
  await receive?.('oblique');
  await page.mouse.move(x,y);
  await page.mouse.down();
  for (const distance of [50,105,150,185,197,204,207,211]) {
    await page.mouse.move(x,y-distance,{steps:4});
    await frame(page);
    const a = await angle();
    assert.ok(Math.abs(a - Math.min(90,32+.28*distance)) < .25, 'camera must follow native pointer movement');
    samples.push({distance,angle:a});
    if (distance === 105 || distance >= 185) await receive?.(distance === 105 ? 'mid-drag' : 'tilt-'+Math.round(a));
  }
  await page.mouse.up();
  await frame(page);
  await receive?.('aligned');
  await page.mouse.move(x,y-211);
  await page.mouse.down();
  await page.mouse.move(x,y-210);
  await frame(page);
  assert.ok(await angle() < 90, 'one-pixel return near alignment');
  await page.mouse.move(x,y-155,{steps:8});
  await page.mouse.up();
  await frame(page);
  const returned = await angle();
  assert.ok(returned < 76 && returned > 70);
  await receive?.('returned');
  await frame(page);
  assert.equal(await angle(), returned, 'release keeps selected angle');
  return samples;
}

async function saveCheck(file, destination) {
  const browser = await launch();
  try {
    const page = await browser.newPage({viewport:{width:800,height:950}});
    await trace(page);
    await page.goto(pathToFileURL(file).href);
    const canvas = page.locator('[data-rotate-terrain][data-state="ready"] canvas');
    await canvas.waitFor({timeout:11000});
    await frame(page);
    const n = await page.locator('script[type="application/json"]').evaluate(el => JSON.parse(el.textContent).n);
    const movement = await drag(page, canvas, key => key === 'aligned' ? canvas.screenshot({path:destination}) : undefined);
    return { movement, ...assertFixed(await page.evaluate(() => window.renderAudit), n) };
  } finally { await browser.close(); }
}

module.exports = { launch, trace, frame, assertFixed, drag };
if (require.main === module) {
  saveCheck(process.argv[3], process.argv[4]).then(result => console.log(JSON.stringify(result))).catch(error => {
    console.error(error);
    process.exitCode = 1;
  });
}
