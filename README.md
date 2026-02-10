# Nano Banana Gradio 工具页

## 功能
- 使用 Gradio 提供网页界面
- 页面采用左右布局：左侧输入，右侧输出
- 支持输入文本（prompt）
- 支持上传多张参考图（urls）
- 文本与参考图至少提供一个
- 下拉菜单包含：模型名、宽高比、分辨率
- 使用 **Gradio 内置登录页鉴权**（账号密码在配置文件中设置）
- 服务监听端口 `45001`，并使用 `root_path=/tools`

## 配置文件使用方式
1. 复制示例文件：
```bash
cp config_example.yaml config.yaml
```
2. 编辑 `config.yaml`：
- `api.endpoint`: 代理接口地址
- `api.key`: 接口密钥
- `auth.username`: Gradio 登录账号
- `auth.password`: Gradio 登录密码
- `request_fields`: 代理接口字段名映射（和文档不一致时改这里）
- `defaults`: 下拉选项默认值与候选值

> 应用启动时实际读取的是 `config.yaml`，`config_example.yaml` 仅作为模板。

## 启动
```bash
pip install -r requirements.txt
python app.py
```

本地直连访问：
- `http://localhost:45001`

Nginx 子路径访问（推荐生产）：
- `https://your-domain/tools/`

## 鉴权说明
- 启动时通过 `launch(auth=(username, password))` 启用 Gradio 原生登录页。
- 用户必须先通过登录页鉴权，才能进入工具页面并调用接口。

## 请求参数说明
默认按以下字段组装请求体（可在 `request_fields` 自定义）：
- `model`: `nano-banana-fast` / `nano-banana` / `nano-banana-pro`
- `prompt`（可选）
- `urls`（可选，多图 data URL 数组）
- `aspectRatio`: `auto` / `1:1` / `16:9` / `9:16` / `4:3` / `3:4` / `3:2` / `2:3` / `5:4` / `4:5` / `21:9`
- `imageSize`: `1K` / `2K` / `4K`

## 说明
- 参考图组件支持多图上传。
- 提交时会校验：`prompt` 与 `urls` 不能同时为空。
- 右侧会优先展示接口返回中的图片（支持 URL 或 Base64），并展示完整 JSON 响应。
