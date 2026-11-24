# 3D 官网二维码 Agent

给官网扫码位做一个可拖拽的立体组件。发一张主体参考图和现有二维码，也可以用目标网址代替二维码。斜视时能看到立体浮雕，向上拖至 90° 时，同一组固定方柱的顶面投影构成二维码。组件提供原码作为备用。

## 本地运行

发布版以 Apple Silicon Mac 为运行环境，包含 Apple Vision 的 ARM64 解码助手及其 [Swift 源码](scripts/read_vision.swift)。请准备 Python 3.9 或更新版本、Node.js、npm 和支持 WebGPU 的 Google Chrome。对话入口需要已登录的 Codex CLI，工作台可直接使用。

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
npm install --no-save --package-lock=false playwright
python app.py
```

- [本地工作台](http://127.0.0.1:8765/)可以用测试网址和自己提供的图片生成早期 3D 预览，也可试用无需上传主体图的环形行星。
- [Agent 对话页](http://127.0.0.1:8765/agent)负责旋转对齐组件。上传一张透明 PNG 或纯色背景主体图，贴上 `https://example.com`，并说明组件放在官网哪里。上传现成二维码时请使用单独一张 PNG 或 JPEG。
- Chrome 安装在自定义目录时，通过 `QR_CHROME` 指定 Chrome 可执行文件。2D 艺术码选项需要额外的本地服务，独立安装本仓库时可保持未勾选。

## 输出与接入

在预览里向上拖到 90°。构建过程会用 Chrome 实际拖动并截取画布，通过 ZXing-C++ 和 Apple Vision 比对扫码载荷后才生成旋转成品。检查记录保存在组件包的 `rotate-scan.json`。

解压组件 ZIP 后，打开 `site.html` 试用。将包内文件放在同一个静态目录，再把 `embed.html` 嵌入到自己的站点。浏览器无法运行立体预览时会显示备用二维码。

Agent 对话文字和主体缩略图交由本机配置的 Codex CLI 处理。二维码图片的解码与比对在本机执行。运行结果保存在 `runs/`，生成的组件包包含参考图和二维码，请在对外分发组件包前检查素材。

## 代码导航

| 文件 | 用途 |
| --- | --- |
| `app.py`、`agent_chat.py` | 本地 HTTP 服务、对话接收和组件导出 |
| `prepare.py`、`rotate_align.py` | 解析二维码、构建固定网格、校验交付画布 |
| `web/rotate-align.js` | WebGPU 渲染和拖动相机 |
| `scripts/rotate-align-browser.cjs` | 浏览器交互和原生画布验收 |
| [旋转对齐二维码交付规范](docs/旋转对齐二维码交付规范.md) | 固定几何和同版成码的验收条件 |

项目代码采用 [MIT License](LICENSE)。来自 Every QR Code 和 DesignQR 的部分保留各自的 [Every QR Code](web/Every-QR-Code-LICENSE.txt) 和 [DesignQR](web/DesignQR-LICENSE.txt) 许可声明。
