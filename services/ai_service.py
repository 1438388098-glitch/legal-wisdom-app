"""AI 问答服务 - 支持 DeepSeek/OpenAI 兼容 API"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "ai_config.json")

DEFAULT_CONFIG = {
    "provider": "deepseek",
    "api_key": "",
    "api_base": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "temperature": 0.3,
    "max_tokens": 2048,
}

_PROVIDERS = {
    "deepseek": {
        "api_base": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "openai": {
        "api_base": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "siliconflow": {
        "api_base": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen2.5-14B-Instruct",
    },
    "zhipu": {
        "api_base": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-plus",
    },
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return dict(DEFAULT_CONFIG)


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


SYSTEM_PROMPT = """你运行在法律智库(Legal Wisdom)个人法条库中。用户正在查阅中国法律法规。请基于现行法律回答。

你是一位精通中国法律的AI助手。请基于以下原则回答用户的提问：

1. 你的回答必须以《中华人民共和国》现行法律法规为依据。
2. 回答时应当引用具体的法律名称和条文编号（如"根据《民法典》第XX条"）。
3. 如果用户的问题涉及多个法律领域，应当综合回答。
4. 如果不确定或没有相关法律依据，请明确说明。
5. 回答应当清晰、准确、通俗易懂。
6. 如果用户提供了具体的法条内容，请基于该内容进行分析。

注意：你的回答仅供参考，不构成法律意见。"""


def build_messages(query, context=None, history=None):
    """构建对话消息"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        messages.extend(history)

    if context:
        messages.append({
            "role": "user",
            "content": f"以下是我查阅的法律条文内容，请基于这些内容回答我的问题。\n\n【相关法律条文】\n{context}\n\n【我的问题】\n{query}"
        })
    else:
        messages.append({"role": "user", "content": query})

    return messages


def ask_ai(query, context=None, config=None, api_key=None, on_stream=None):
    """
    调用 AI API，返回完整回答文本。
    on_stream: 可选回调函数，接收逐块文本
    """
    if config is None:
        config = load_config()

    api_key = api_key or config.get("api_key", "")
    if not api_key:
        return "Error: API Key not configured. Please add one in Settings."

    provider = config.get("provider", "deepseek")
    custom_base = config.get("api_base", "").strip()
    custom_model = config.get("model", "").strip()
    if provider == "custom":
        if not custom_base:
            return "Error: Custom provider requires an API Base URL."
        base_url = custom_base
        model = custom_model or "unknown"
    else:
        base_url = custom_base or _PROVIDERS.get(provider, {}).get("api_base", DEFAULT_CONFIG["api_base"])
        model = custom_model or _PROVIDERS.get(provider, {}).get("model", DEFAULT_CONFIG["model"])
    temperature = config.get("temperature", 0.3)
    max_tokens = config.get("max_tokens", 2048)

    messages = build_messages(query, context)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept-Encoding": "identity",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": on_stream is not None,
    }

    import urllib.request
    import urllib.error

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        if on_stream:
            return _stream_response(req, on_stream)
        else:
            return _sync_response(req)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return f"API request failed (HTTP {e.code}): {body[:200]}"
    except Exception as e:
        return f"Request error: {str(e)}"


def _sync_response(req):
    import urllib.request
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    choices = result.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "").strip()
    return "AI returned empty response"


def _stream_response(req, on_stream):
    import urllib.request
    full_text = ""
    with urllib.request.urlopen(req, timeout=120) as resp:
        for line in resp:
            line = line.decode("utf-8", errors="replace").strip()
            if not line or line.startswith(":"):
                continue
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        full_text += content
                        on_stream(content)
                except json.JSONDecodeError:
                    continue
    return full_text.strip()
