const form = document.querySelector('#agent-form');
const message = document.querySelector('#message');
const attachments = document.querySelector('#attachments');
const attachmentText = document.querySelector('#attachment-text');
const clear = document.querySelector('#clear-attachments');
const send = document.querySelector('#send');
const log = document.querySelector('#conversation');
const status = document.querySelector('#agent-status');
const labels = {preview:'打开官网预览', component:'下载嵌入组件', art:'下载彩色艺术码', backup:'下载备用码', guide:'下载接入说明'};
let turns = [];
let files = [];

function addTurn(speaker, text, links) {
  const item = document.createElement('li');
  item.className = 'agent-turn ' + speaker;
  const name = document.createElement('strong');
  name.textContent = speaker === 'user' ? '你' : '3D 二维码 Agent';
  const content = document.createElement('p');
  content.textContent = text;
  item.append(name, content);
  if (links) {
    const group = document.createElement('div');
    group.className = 'agent-files';
    for (const [key, label] of Object.entries(labels)) {
      if (!links[key]) continue;
      const link = document.createElement('a');
      link.href = links[key];
      link.textContent = label;
      link.dataset.artifact = key;
      if (key !== 'preview') link.download = '';
      group.append(link);
    }
    item.append(group);
  }
  log.append(item);
}

function encode(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('无法读取附件。'));
    reader.onload = () => resolve({name:file.name, data:String(reader.result).split(',')[1]});
    reader.readAsDataURL(file);
  });
}

attachments.addEventListener('change', () => {
  for (const file of attachments.files) {
    files = [...files.filter(previous => previous.name !== file.name), file].slice(-2);
  }
  attachmentText.textContent = files.map(file => file.name).join(' · ');
  clear.hidden = !files.length;
});

clear.addEventListener('click', () => {
  files = [];
  attachments.value = '';
  attachmentText.textContent = '';
  clear.hidden = true;
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  const text = message.value.trim();
  if (!text || send.disabled) return;
  if (files.some(file => file.size > 8 * 1024 * 1024)) {
    status.textContent = '每张附件请使用 8 MiB 以内的文件。';
    return;
  }
  send.disabled = message.readOnly = attachments.disabled = clear.disabled = true;
  status.textContent = '正在理解需求并准备交付物…';
  try {
    const uploads = await Promise.all(files.map(encode));
    const response = await fetch('/api/agent', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({messages:[...turns, text], uploads}),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '对话请求失败。');
    addTurn('user', [text, ...files.map(file => file.name)].join('\n'));
    addTurn('assistant', result.reply, result.links);
    turns = result.run ? [] : [...turns, text].slice(-7);
    if (result.run) {
      files = [];
      attachments.value = '';
      attachmentText.textContent = '';
      clear.hidden = true;
    }
    message.value = '';
    status.textContent = '';
  } catch (error) {
    status.textContent = error.message || '对话请求失败。';
  } finally {
    send.disabled = message.readOnly = attachments.disabled = clear.disabled = false;
    message.focus();
  }
});
