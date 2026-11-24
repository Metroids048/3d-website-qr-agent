/* Fixed terrain projection, column faces, shading, and pointer handling adapted from
   Every QR Code (ed404c6) and the approved rotate-align patch. See Every-QR-Code-LICENSE.txt. */
"use strict";
function attachTerrainDrag(canvas, getView, setView) {
    const listeners = new AbortController();
    const options = { signal: listeners.signal };
    const originalTouchAction = canvas.style.touchAction;
    const originalCursor = canvas.style.cursor;
    canvas.style.touchAction = "none";
    canvas.style.cursor = "grab";
    let drag = null;
    const limit = (value, lo, hi) => Math.max(lo, Math.min(hi, value));
    canvas.addEventListener("pointerdown", (event) => {
        if (event.button !== 0 || !event.isPrimary || drag)
            return;
        drag = {
            id: event.pointerId,
            x: event.clientX,
            y: event.clientY,
            pan: event.shiftKey || canvas.dataset["dragMode"] === "pan",
            initial: getView(),
        };
        canvas.setPointerCapture(event.pointerId);
        canvas.style.cursor = "grabbing";
    }, options);
    canvas.addEventListener("pointermove", (event) => {
        if (!drag || event.pointerId !== drag.id)
            return;
        const dx = event.clientX - drag.x;
        const dy = event.clientY - drag.y;
        const [yaw, elevation, x, y] = drag.initial;
        if (drag.pan) {
            setView([
                yaw,
                elevation,
                limit(x + dx * 2 / Math.max(1, canvas.clientWidth), -0.12, 0.12),
                limit(y - dy * 2 / Math.max(1, canvas.clientHeight), -0.12, 0.12),
            ]);
            return;
        }
        setView([yaw + dx * 0.012, elevation - dy * 0.28, x, y]);
    }, options);
    const finish = (event) => {
        if (!drag || event.pointerId !== drag.id)
            return;
        drag = null;
        canvas.style.cursor = "grab";
    };
    canvas.addEventListener("pointerup", finish, options);
    canvas.addEventListener("pointercancel", finish, options);
    canvas.addEventListener("lostpointercapture", finish, options);
    return () => {
        listeners.abort();
        canvas.style.touchAction = originalTouchAction;
        canvas.style.cursor = originalCursor;
        if (drag && canvas.hasPointerCapture(drag.id))
            canvas.releasePointerCapture(drag.id);
    };
}

const terrainShader = /* wgsl */ `
struct Camera {
  view: vec4f,
  framing: vec4f,
}
struct Terrain {
  shape: vec4f,
  material: vec4f,
}
struct Column {
  side: vec4f,
  top: vec4f,
}
struct Surface {
  @builtin(position) position: vec4f,
  @location(0) world: vec3f,
  @location(1) @interpolate(flat) face: u32,
  @location(2) @interpolate(flat) side: vec3f,
  @location(3) @interpolate(flat) top: vec3f,
  @location(4) fraction: f32,
  @location(5) @interpolate(flat) painted: f32,
}
@group(0) @binding(0) var<uniform> camera: Camera;
@group(0) @binding(1) var<storage, read> columns: array<Column>;
@group(0) @binding(2) var<uniform> scene: Terrain;
@group(0) @binding(3) var artwork: texture_2d<f32>;
@group(0) @binding(4) var brush: sampler;

fn project(position: vec3f) -> vec4f {
  let tilt = radians(camera.view.y);
  let yaw = camera.view.x + scene.shape.y * (1.0 - smoothstep(32.0, 90.0, camera.view.y));
  let across = position.x * cos(yaw) + position.z * sin(yaw);
  let away = position.z * cos(yaw) - position.x * sin(yaw);
  let up = (position.y - scene.shape.z) * cos(tilt) - away * sin(tilt);
  let depth = -(position.y * sin(tilt) + away * cos(tilt));
  return vec4f(vec2f(across, up) * camera.framing.xy + camera.view.zw, depth * 0.5 + 0.5, 1.0);
}

@vertex
fn vertexMain(@builtin(vertex_index) vertex: u32, @builtin(instance_index) id: u32) -> Surface {
  let face = vertex / 6u;
  let quad = array<vec2f, 6>(
    vec2f(0.0, 0.0), vec2f(1.0, 0.0), vec2f(0.0, 1.0),
    vec2f(0.0, 1.0), vec2f(1.0, 0.0), vec2f(1.0, 1.0)
  );
  let uv = quad[vertex % 6u];
  let cell = columns[id];
  let height = cell.side.w;
  let n = u32(scene.shape.x);
  let center = (vec2f(f32(id % n), f32(id / n)) + 0.5) / scene.shape.x - 0.5;
  var local: vec3f;
  switch face {
    case 0u: { local = vec3f(uv.x - 0.5, height, uv.y - 0.5); }
    case 1u: { local = vec3f(uv.x - 0.5, uv.y * height, 0.5); }
    case 2u: { local = vec3f(0.5 - uv.x, uv.y * height, -0.5); }
    case 3u: { local = vec3f(0.5, uv.y * height, 0.5 - uv.x); }
    default: { local = vec3f(-0.5, uv.y * height, uv.x - 0.5); }
  }
  let world = vec3f(center.x + local.x / scene.shape.x, local.y, center.y + local.z / scene.shape.x);
  var output: Surface;
  output.position = project(world);
  output.world = world;
  output.face = face;
  output.side = cell.side.rgb;
  output.top = cell.top.rgb;
  output.fraction = uv.y;
  output.painted = cell.top.w;
  return output;
}

@fragment
fn fragmentMain(input: Surface) -> @location(0) vec4f {
  if (input.face == 0u) { return vec4f(input.top, 1.0); }
  let shade = array<f32, 5>(1.0, 0.96, 0.74, 0.68, 0.82)[input.face];
  var color = input.side * shade * mix(0.70, 1.0, input.fraction);
  let uv = vec2f(input.world.x / scene.material.x + 0.5, 1.0 - (input.world.y - 0.018) / scene.shape.w);
  if (input.face == 1u && input.painted > 0.5 && all(uv >= vec2f(0.0)) && all(uv <= vec2f(1.0))) {
    let ink = textureSampleLevel(artwork, brush, uv, 0.0);
    color = mix(color, ink.rgb, ink.a);
  }
  return vec4f(color, 1.0);
}
`;

function packedBuffer(device, label, data, usage) {
  const buffer = device.createBuffer({ label, size: data.byteLength, usage, mappedAtCreation: true });
  new Float32Array(buffer.getMappedRange()).set(data);
  buffer.unmap();
  return buffer;
}

async function mountTerrain(host) {
  const scene = JSON.parse(host.querySelector('script').textContent);
  const canvas = host.querySelector('canvas');
  const slider = host.querySelector('input');
  const readout = host.querySelector('output');
  const status = host.querySelector('[role="status"]');
  const adapter = await navigator.gpu?.requestAdapter();
  if (!adapter) throw Error('WebGPU unavailable');
  const device = await adapter.requestDevice();
  const context = canvas.getContext('webgpu');
  if (!context) throw Error('WebGPU canvas unavailable');
  const format = navigator.gpu.getPreferredCanvasFormat();
  context.configure({ device, format, alphaMode: 'opaque' });
  const module = device.createShaderModule({label:'Every QR Code fixed terrain', code: terrainShader});
  const pipeline = await device.createRenderPipelineAsync({
    label: 'Fixed terrain', layout: 'auto', vertex: { module, entryPoint: 'vertexMain' },
    fragment: { module, entryPoint: 'fragmentMain', targets: [{ format }] },
    depthStencil: { format: 'depth24plus', depthWriteEnabled: true, depthCompare: 'less' },
  });
  const geometry = packedBuffer(device, 'terrain-columns', Float32Array.from(scene.columns), GPUBufferUsage.STORAGE);
  const constants = packedBuffer(device, 'terrain-shape',
    Float32Array.of(scene.n, scene.yaw, scene.center, scene.portraitHeight, scene.portraitWidth, 0, 0, 0), GPUBufferUsage.UNIFORM);
  const camera = device.createBuffer({
    label: 'terrain-camera', size: 32, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  });
  const source = new Image();
  source.src = scene.texture;
  await source.decode();
  const texture = device.createTexture({
    label: 'terrain-material', size: [source.naturalWidth, source.naturalHeight],
    format: 'rgba8unorm',
    usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST | GPUTextureUsage.RENDER_ATTACHMENT,
  });
  device.queue.copyExternalImageToTexture({source}, {texture}, [source.naturalWidth, source.naturalHeight]);
  const group = device.createBindGroup({
    layout: pipeline.getBindGroupLayout(0), entries: [
      {binding:0, resource:{buffer:camera}}, {binding:1, resource:{buffer:geometry}},
      {binding:2, resource:{buffer:constants}}, {binding:3, resource:texture.createView()},
      {binding:4, resource:device.createSampler({magFilter:'linear', minFilter:'linear'})},
    ],
  });
  let view = [0, 32, 0, 0];
  let depth;
  let frame = 0;
  function paint() {
    frame = 0;
    const ratio = Math.max(1, Math.min(devicePixelRatio, 2));
    const width = Math.max(1, Math.round(canvas.clientWidth * ratio));
    const height = Math.max(1, Math.round(canvas.clientHeight * ratio));
    if (!depth || width !== canvas.width || height !== canvas.height) {
      canvas.width = width;
      canvas.height = height;
      depth?.destroy();
      depth = device.createTexture({ size:[width,height], format:'depth24plus', usage:GPUTextureUsage.RENDER_ATTACHMENT });
    }
    const aspect = width / height;
    const transition = Math.max(0, Math.min(1, (view[1] - 32) / 58));
    const yaw = view[0] + scene.yaw * (1 - transition * transition * (3 - 2 * transition));
    const widthInView = Math.abs(Math.sin(yaw)) + Math.abs(Math.cos(yaw));
    const nearTop = Math.max(0, (view[1] - 65) / 25);
    const fit = 1 + nearTop * (widthInView - 1);
    const scale = Math.min(1.90 / (1 + 8 / scene.n) / fit, 1.82 / widthInView);
    device.queue.writeBuffer(camera, 0, Float32Array.of(...view,
      scale / Math.max(1, aspect), scale / Math.max(1, 1 / aspect), 0, 0));
    const encoder = device.createCommandEncoder();
    const pass = encoder.beginRenderPass({
      colorAttachments:[{view:context.getCurrentTexture().createView(), loadOp:'clear', storeOp:'store',
        clearValue:{r:0.983,g:0.973,b:0.948,a:1}}],
      depthStencilAttachment:{view:depth.createView(), depthClearValue:1, depthLoadOp:'clear', depthStoreOp:'store'},
    });
    pass.setPipeline(pipeline);
    pass.setBindGroup(0, group);
    pass.draw(30, scene.n * scene.n);
    pass.end();
    device.queue.submit([encoder.finish()]);
    canvas.dataset.angle = String(view[1]);
  }
  const schedule = () => { if (!frame) frame = requestAnimationFrame(paint); };
  function setView([yaw, elevation, x, y]) {
    const angle = Math.min(90, Math.max(15, elevation));
    view = [yaw, angle, x, y];
    const rounded = angle === 90 ? 90 : Math.min(89, Math.round(angle));
    slider.value = String(rounded);
    slider.setAttribute('aria-valuetext', rounded + '°');
    readout.value = rounded + '°';
    host.dataset.aligned = String(angle === 90);
    schedule();
  }
  const detach = attachTerrainDrag(canvas, () => view, setView);
  host.querySelector('[data-pan]').addEventListener('click', (event) => {
    const pan = canvas.dataset.dragMode !== 'pan';
    canvas.dataset.dragMode = pan ? 'pan' : 'orbit';
    event.currentTarget.setAttribute('aria-pressed', String(pan));
  });
  host.querySelector('[data-reset]').addEventListener('click', () => {
    canvas.dataset.dragMode = 'orbit';
    host.querySelector('[data-pan]').setAttribute('aria-pressed','false');
    setView([0, 32, 0, 0]);
  });
  slider.addEventListener('input', () => setView([view[0], slider.valueAsNumber, view[2], view[3]]));
  canvas.addEventListener('keydown', (event) => {
    const delta = {ArrowUp:[0,3], ArrowDown:[0,-3], ArrowLeft:[-.08,0], ArrowRight:[.08,0]}[event.key];
    if (!delta) return;
    event.preventDefault();
    setView([view[0]+delta[0], view[1]+delta[1], view[2], view[3]]);
  });
  const resize = new ResizeObserver(schedule);
  resize.observe(canvas);
  device.lost.then(() => {
    detach();
    resize.disconnect();
    cancelAnimationFrame(frame);
    host.dataset.state = 'fallback';
    status.textContent = '立体预览已中断，请使用备用码。';
  });
  status.textContent = '';
  host.dataset.state = 'ready';
  setView(view);
}

for (const host of document.querySelectorAll('[data-rotate-terrain]')) {
  mountTerrain(host).catch(error => {
    console.error(error);
    host.dataset.state = 'fallback';
    host.querySelector('[role="status"]').textContent = '此环境无法启用立体预览，请使用备用码。';
  });
}
