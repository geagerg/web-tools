# Nano Banana Pro Gradio 工具页

## 功能
- 使用 Gradio 提供网页界面
- 支持输入文本（prompt）
- 支持上传多张参考图（reference images）
- 文本与参考图至少提供一个
- 接口 `endpoint` 与 `key` 放在 `config_example.yaml`
- 服务监听端口 `45001`

## 配置
编辑 `config_example.yaml`：
- `api.endpoint`: Nano Banana Pro 接口地址
- `api.key`: Nano Banana Pro 接口密钥
- `defaults`: 下拉选项默认值与候选值

## 启动
```bash
pip install -r requirements.txt
python app.py
```

启动后访问：
- `http://localhost:45001`

## 说明
- 参考图组件支持多图上传。
- 提交时会校验：`prompt` 与 `reference_images` 不能同时为空。
