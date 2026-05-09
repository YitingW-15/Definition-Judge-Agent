import os
import yaml
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

_config = None
_clients = {}


def _load_config():
    global _config
    if _config is None:
        cfg_path = os.path.join(os.path.dirname(__file__), "../../config/models.yaml")
        with open(cfg_path, "r", encoding="utf-8") as f:
            _config = yaml.safe_load(f)
    return _config


def _get_client(provider: str) -> OpenAI:
    if provider not in _clients:
        cfg = _load_config()["providers"][provider]
        api_key = os.environ.get(cfg["api_key_env"])
        if not api_key:
            raise ValueError(f"环境变量 {cfg['api_key_env']} 未设置")
        _clients[provider] = OpenAI(api_key=api_key, base_url=cfg["base_url"])
    return _clients[provider]


def chat(role: str, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
    """
    role: 对应 models.yaml 中的角色名，如 'generator', 'evaluator'
    """
    cfg = _load_config()
    model_cfg = cfg["models"][role][0]
    client = _get_client(model_cfg["provider"])

    response = client.chat.completions.create(
        model=model_cfg["name"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    msg = response.choices[0].message
    content = msg.content or getattr(msg, "reasoning_content", "") or ""
    return content.strip()
