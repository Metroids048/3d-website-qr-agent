"use strict";
const form = document.querySelector("#build-form");
const feedback = document.querySelector("#build-status");
const submit = document.querySelector("#build-button");
const backup = document.querySelector("#backup-file");
const purpose = form.querySelector('#purpose');
const source = form.querySelector('#qr-source');
const shape = form.querySelector('#shape');
const qrInput = form.querySelector('#qr');
const urlInput = form.querySelector('#url');
const textInput = form.querySelector('#payload-text');
const briefInput = form.querySelector('#brief');
const subjectInput = form.querySelector('#subject');
const artworkInput = form.querySelector("#artwork");
const uploadShapes = ['photo', 'nasa', 'volume', 'mascot', 'bottle'];
const maxBytes = 8 * 1024 * 1024;
let backupUrl;

function showField(input, enabled) {
  input.closest('.field').hidden = !enabled;
  input.disabled = !enabled;
  input.required = enabled;
}

function updateFields() {
  const wechat = purpose.value === 'wechat-follow';
  for (const option of shape.options) option.disabled = wechat && !uploadShapes.includes(option.value);
  if (wechat && !uploadShapes.includes(shape.value)) shape.value = 'photo';
  const isWebsite = shape.value === 'logo-site';
  if (isWebsite) source.value = 'url';
  if (wechat) source.value = 'image';
  source.disabled = wechat || isWebsite;
  form.elements.placement.required = wechat;
  showField(qrInput, source.value === 'image');
  showField(urlInput, source.value === 'url');
  showField(textInput, source.value === 'text');
  showField(subjectInput, uploadShapes.includes(shape.value));
  artworkInput.disabled = subjectInput.disabled && !isWebsite;
  artworkInput.closest('.field').hidden = artworkInput.disabled;
  showField(briefInput, shape.value === 'character');
  urlInput.placeholder = isWebsite ? 'https://www.python.org/' : 'https://example.com';
}
source.addEventListener('change', updateFields);
shape.addEventListener('change', updateFields);
purpose.addEventListener('change', updateFields);
updateFields();

function read(file) {
  if (file.size > maxBytes) throw new Error("每张图片须小于 8 MiB。");
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({name: file.name, data: reader.result.split(",")[1]});
    reader.onerror = () => reject(new Error("图片无法读取，请重新选择。"));
    reader.readAsDataURL(file);
  });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  if (backupUrl) URL.revokeObjectURL(backupUrl);
  const qrFile = data.get("qr");
  backupUrl = qrFile ? URL.createObjectURL(qrFile) : null;
  if (backupUrl) {
    backup.href = backupUrl;
    backup.download = qrFile.name;
  }
  backup.hidden = true;
  submit.disabled = true;
  feedback.hidden = false;
  feedback.textContent = data.has("artwork") ? "正在制作立体组件，并生成和校验 2D 艺术码…" : "正在读取二维码并排布方块…";
  try {
    const payload = {preset: data.get("preset"), title: data.get("title"), placement: data.get("placement")};
    if (data.get("purpose") !== "general") payload.purpose = data.get("purpose");
    if (data.get("palette")) payload.palette = data.get("palette");
    if (data.has("artwork")) payload.artwork = true;
    if (data.get("effect")) payload.effect = data.get("effect");
    const [subject, qr] = await Promise.all([
      data.has("subject") ? read(data.get("subject")) : null,
      qrFile ? read(qrFile) : null,
    ]);
    if (subject) payload.subject = subject;
    if (data.has("brief")) payload.brief = data.get("brief");
    if (qr) payload.qr = qr;
    else if (data.has("payloadText")) payload.payloadText = data.get("payloadText");
    else payload.url = data.get("url");
    const response = await fetch("/api/build", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    if (payload.artwork && !result.artwork) {
      throw new Error("当前工作台版本未返回 2D 艺术码，请使用更新后的工作台。");
    }
    window.location.assign(result.page);
  } catch (error) {
    feedback.textContent = error instanceof TypeError ? "无法连接本地工作台，请稍后再试。" : error.message;
    backup.hidden = !backupUrl;
    submit.disabled = false;
  }
});
