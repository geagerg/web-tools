from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any

import gradio as gr
import requests
import yaml
from PIL import Image

CONFIG_PATH = Path("config_example.yaml")


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    if "api" not in cfg or "endpoint" not in cfg["api"] or "key" not in cfg["api"]:
        raise ValueError("config_example.yaml must include api.endpoint and api.key")
    return cfg


def pil_to_base64(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def decode_base64_image(image_data: str) -> Image.Image | None:
    try:
        if image_data.startswith("data:"):
            image_data = image_data.split(",", 1)[1]
        binary = base64.b64decode(image_data)
        return Image.open(io.BytesIO(binary)).convert("RGB")
    except Exception:
        return None


def find_image_payload(data: Any) -> str | None:
    if isinstance(data, str):
        if data.startswith("http://") or data.startswith("https://") or data.startswith("data:image"):
            return data
        return None

    if isinstance(data, list):
        for item in data:
            found = find_image_payload(item)
            if found:
                return found
        return None

    if isinstance(data, dict):
        preferred_keys = [
            "image",
            "image_url",
            "url",
            "image_base64",
            "b64_json",
            "output",
            "data",
            "result",
            "results",
            "images",
        ]
        for key in preferred_keys:
            if key in data:
                found = find_image_payload(data[key])
                if found:
                    return found

        for value in data.values():
            found = find_image_payload(value)
            if found:
                return found

    return None


def materialize_image(image_payload: str) -> Image.Image | None:
    if image_payload.startswith("http://") or image_payload.startswith("https://"):
        try:
            response = requests.get(image_payload, timeout=30)
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content)).convert("RGB")
        except requests.RequestException:
            return None

    return decode_base64_image(image_payload)


def call_nano_banana_pro(
    prompt: str,
    images: list[Image.Image] | None,
    model: str,
    output_format: str,
    style: str,
) -> tuple[Image.Image | None, str]:
    cfg = load_config()
    endpoint = cfg["api"]["endpoint"]
    api_key = cfg["api"]["key"]

    prompt = (prompt or "").strip()
    images = images or []

    if not prompt and not images:
        return None, "❌ 参数错误：文本和参考图至少提供一个。"

    payload: dict[str, Any] = {
        "model": model,
        "output_format": output_format,
        "style": style,
    }

    if prompt:
        payload["prompt"] = prompt

    if images:
        payload["reference_images"] = [pil_to_base64(img) for img in images]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=90)
        response.raise_for_status()
    except requests.RequestException as exc:
        return None, f"❌ 接口请求失败: {exc}"

    try:
        data = response.json()
    except ValueError:
        return None, response.text

    image_payload = find_image_payload(data)
    image = materialize_image(image_payload) if image_payload else None
    formatted_json = json.dumps(data, ensure_ascii=False, indent=2)
    return image, formatted_json


def build_ui() -> gr.Blocks:
    cfg = load_config()
    defaults = cfg.get("defaults", {})

    model_options = defaults.get("model_options", ["nano-banana-pro"])
    format_options = defaults.get("output_format_options", ["url", "base64"])
    style_options = defaults.get("style_options", ["default", "photoreal", "anime"])

    with gr.Blocks(title="Nano Banana Pro 工具页") as demo:
        gr.Markdown("## Nano Banana Pro 生成页\n支持文本 + 多张参考图（至少一个必填）")

        with gr.Row(equal_height=True):
            with gr.Column(scale=1):
                prompt = gr.Textbox(label="文本提示词（可选）", lines=4, placeholder="输入你想生成的内容")
                images = gr.Gallery(label="参考图（可选，可上传多张）", type="pil")

                with gr.Row():
                    model = gr.Dropdown(
                        label="模型",
                        choices=model_options,
                        value=defaults.get("model", model_options[0]),
                    )
                    output_format = gr.Dropdown(
                        label="输出格式",
                        choices=format_options,
                        value=defaults.get("output_format", format_options[0]),
                    )
                    style = gr.Dropdown(
                        label="风格",
                        choices=style_options,
                        value=defaults.get("style", style_options[0]),
                    )

                submit = gr.Button("提交", variant="primary")

            with gr.Column(scale=1):
                result_image = gr.Image(label="输出图片", type="pil")
                result_text = gr.Code(label="接口响应", language="json")

        submit.click(
            fn=call_nano_banana_pro,
            inputs=[prompt, images, model, output_format, style],
            outputs=[result_image, result_text],
        )

    return demo


if __name__ == "__main__":
    app = build_ui()
    app.launch(server_name="0.0.0.0", server_port=45001, root_path="/tools")
