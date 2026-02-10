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

CONFIG_PATH = Path("config.yaml")
CONFIG_EXAMPLE_PATH = Path("config_example.yaml")

PREVIEW_CSS = """
#ref-preview .grid-container {
  grid-template-columns: repeat(auto-fill, 96px) !important;
  justify-content: flex-start !important;
  gap: 8px !important;
}

#ref-preview .grid-container img {
  width: 96px !important;
  height: 96px !important;
  object-fit: cover !important;
}
"""


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}. 请先复制 {CONFIG_EXAMPLE_PATH} 为 {CONFIG_PATH} 并填写配置。"
        )

    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    if "api" not in cfg or "endpoint" not in cfg["api"] or "key" not in cfg["api"]:
        raise ValueError("config.yaml must include api.endpoint and api.key")

    auth_cfg = cfg.get("auth", {})
    if "username" not in auth_cfg or "password" not in auth_cfg:
        raise ValueError("config.yaml must include auth.username and auth.password")

    return cfg


def pil_to_base64(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def pil_to_data_url(image: Image.Image) -> str:
    return f"data:image/png;base64,{pil_to_base64(image)}"


def load_reference_images(image_paths: list[str] | None) -> list[Image.Image]:
    loaded_images: list[Image.Image] = []
    for path in image_paths or []:
        try:
            loaded_images.append(Image.open(path).convert("RGB"))
        except Exception:
            continue
    return loaded_images


def build_image_previews(image_paths: list[str] | None) -> list[Image.Image]:
    return load_reference_images(image_paths)


def file_item_to_path(file_item: Any) -> str | None:
    if isinstance(file_item, str):
        return file_item
    if hasattr(file_item, "name"):
        return str(file_item.name)
    if isinstance(file_item, dict) and "name" in file_item:
        return str(file_item["name"])
    return None


def append_reference_files(new_files: Any, current_paths: list[str] | None) -> tuple[list[str], list[Image.Image], str]:
    paths = list(current_paths or [])
    files = new_files if isinstance(new_files, list) else [new_files]

    for file_item in files:
        path = file_item_to_path(file_item)
        if path and path not in paths:
            paths.append(path)

    previews = build_image_previews(paths)
    status_text = f"已上传 {len(previews)} 张参考图"
    return paths, previews, status_text


def clear_reference_files() -> tuple[list[str], list[Image.Image], str]:
    return [], [], "已上传 0 张参考图"


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
            "urls",
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


def parse_response_payload(response: requests.Response) -> dict[str, Any] | None:
    try:
        return response.json()
    except ValueError:
        text = response.text or ""
        last_event: dict[str, Any] | None = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line.startswith("data:"):
                continue
            content = line[5:].strip()
            if not content:
                continue
            try:
                maybe_json = json.loads(content)
            except ValueError:
                continue
            if isinstance(maybe_json, dict):
                last_event = maybe_json
        return last_event


def build_payload(
    prompt: str,
    images: list[Image.Image],
    model: str,
    aspect_ratio: str,
    image_size: str,
    request_fields: dict[str, str],
) -> dict[str, Any]:
    model_field = request_fields.get("model", "model")
    prompt_field = request_fields.get("prompt", "prompt")
    images_field = request_fields.get("images", "urls")
    aspect_ratio_field = request_fields.get("aspect_ratio", "aspectRatio")
    image_size_field = request_fields.get("image_size", "imageSize")

    payload: dict[str, Any] = {
        model_field: model,
        aspect_ratio_field: aspect_ratio,
        image_size_field: image_size,
    }

    if prompt:
        payload[prompt_field] = prompt

    if images:
        payload[images_field] = [pil_to_data_url(img) for img in images]

    return payload


def format_debug_output(
    request_payload: dict[str, Any],
    response_payload: dict[str, Any] | None = None,
    raw_response: str | None = None,
    error: str | None = None,
) -> str:
    content: dict[str, Any] = {"request_payload": request_payload}
    if response_payload is not None:
        content["response_payload"] = response_payload
    if raw_response:
        content["raw_response"] = raw_response
    if error:
        content["error"] = error
    return json.dumps(content, ensure_ascii=False, indent=2)


def call_nano_banana_pro(
    prompt: str,
    image_paths: list[str] | None,
    model: str,
    aspect_ratio: str,
    image_size: str,
) -> tuple[Image.Image | None, str]:
    cfg = load_config()
    endpoint = cfg["api"]["endpoint"]
    api_key = cfg["api"]["key"]
    request_fields = cfg.get("request_fields", {})

    prompt = (prompt or "").strip()
    images = load_reference_images(image_paths)

    if not prompt and not images:
        return None, "❌ 参数错误：文本和参考图至少提供一个。"

    payload = build_payload(
        prompt=prompt,
        images=images,
        model=model,
        aspect_ratio=aspect_ratio,
        image_size=image_size,
        request_fields=request_fields,
    )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=90)
        response.raise_for_status()
    except requests.RequestException as exc:
        return None, format_debug_output(request_payload=payload, error=f"接口请求失败: {exc}")

    data = parse_response_payload(response)
    if data is None:
        return None, format_debug_output(request_payload=payload, raw_response=response.text)

    image_payload = find_image_payload(data)
    image = materialize_image(image_payload) if image_payload else None
    return image, format_debug_output(request_payload=payload, response_payload=data)


def build_ui() -> gr.Blocks:
    cfg = load_config()
    defaults = cfg.get("defaults", {})

    model_options = defaults.get("model_options", ["nano-banana-fast", "nano-banana", "nano-banana-pro"])
    aspect_ratio_options = defaults.get(
        "aspect_ratio_options",
        ["auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "21:9"],
    )
    image_size_options = defaults.get("image_size_options", ["1K", "2K", "4K"])

    with gr.Blocks(title="Nano Banana Pro 工具页") as demo:
        gr.Markdown("## Nano Banana 生成页\n支持文本 + 多张参考图（至少一个必填）")

        reference_paths = gr.State([])

        with gr.Row():
            with gr.Column(scale=1):
                prompt = gr.Textbox(label="文本提示词（可选）", lines=4, placeholder="输入你想生成的内容")
                upload_refs = gr.UploadButton(
                    "拖拽或点击上传参考图（可连续添加）",
                    file_count="multiple",
                    file_types=["image"],
                    size="sm",
                )
                clear_refs = gr.Button("清空参考图", size="sm")
                ref_status = gr.Markdown("已上传 0 张参考图")
                image_previews = gr.Gallery(
                    label="参考图预览",
                    columns=4,
                    height=220,
                    object_fit="cover",
                    elem_id="ref-preview",
                )

                with gr.Row():
                    model = gr.Dropdown(
                        label="模型名",
                        choices=model_options,
                        value=defaults.get("model", model_options[0]),
                    )
                    aspect_ratio = gr.Dropdown(
                        label="宽高比",
                        choices=aspect_ratio_options,
                        value=defaults.get("aspect_ratio", aspect_ratio_options[0]),
                    )
                    image_size = gr.Dropdown(
                        label="分辨率",
                        choices=image_size_options,
                        value=defaults.get("image_size", image_size_options[0]),
                    )

                submit = gr.Button("提交", variant="primary", size="sm")

            with gr.Column(scale=1):
                result_image = gr.Image(label="输出图片", type="pil", height=520)
                result_text = gr.Code(label="接口响应（调试）", language="json", lines=8)

        upload_refs.upload(
            fn=append_reference_files,
            inputs=[upload_refs, reference_paths],
            outputs=[reference_paths, image_previews, ref_status],
        )

        clear_refs.click(
            fn=clear_reference_files,
            outputs=[reference_paths, image_previews, ref_status],
        )

        submit.click(
            fn=call_nano_banana_pro,
            inputs=[prompt, reference_paths, model, aspect_ratio, image_size],
            outputs=[result_image, result_text],
        )

    return demo


if __name__ == "__main__":
    cfg = load_config()
    auth_username = str(cfg["auth"]["username"])
    auth_password = str(cfg["auth"]["password"])

    app = build_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=45001,
        root_path="/tools",
        auth=(auth_username, auth_password),
        auth_message="请输入访问账号和密码",
        css=PREVIEW_CSS,
    )
