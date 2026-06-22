"""
llm_client.py
-------------
Provider-agnostic chat client for the recommendation engine.

Default mode is "auto": prefer a local **llama.cpp server** (GPU, via Vulkan/CUDA)
if one is reachable, otherwise fall back to an in-process GGUF model
(llama-cpp-python, CPU). The same `chat()` interface also targets any
OpenAI-compatible endpoint, so swapping to a cloud provider (e.g. Claude) is a
config change, not a code change.

Recommended GPU setup (no installs needed — uses the bundled llama.cpp):
  E:\\odysseus\\binaries\\llama_server\\llama-server.exe ^
    -m E:\\odysseus\\data\\models\\Qwen3-4B-Instruct-2507-Q4_K_M.gguf ^
    -ngl 99 -c 4096 --host 127.0.0.1 --port 8080

Env vars (all optional):
  LLM_PROVIDER     auto | openai | local | none      (default: auto)
  LLM_BASE_URL     OpenAI-compatible base url         (default: http://127.0.0.1:8080/v1)
  LLM_API_KEY      bearer token                       (default: none)
  LLM_MODEL        model name sent to the server      (default: local-model)
  LLM_MODEL_PATH   .gguf path for the CPU fallback    (default: bundled Qwen3-4B)
  LLM_N_CTX        context window for the fallback    (default: 4096)
"""

import os
import time
import threading

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "auto").lower()
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8080/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY")
LLM_MODEL = os.environ.get("LLM_MODEL", "local-model")
LLM_MODEL_PATH = os.environ.get(
    "LLM_MODEL_PATH",
    r"E:\odysseus\data\models\Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
)
LLM_N_CTX = int(os.environ.get("LLM_N_CTX", "4096"))

_model = None              # in-process fallback model
_lock = threading.Lock()
_server_ok = None          # cached server reachability
_server_checked = 0.0


def _server_reachable() -> bool:
    """Cheap, cached health check for the local llama.cpp server."""
    global _server_ok, _server_checked
    now = time.time()
    if _server_ok is not None and (now - _server_checked) < 30:
        return _server_ok
    try:
        import requests
        requests.get(f"{LLM_BASE_URL.rstrip('/')}/models", timeout=1.5)
        _server_ok = True
    except Exception:
        _server_ok = False
    _server_checked = now
    return _server_ok


def _effective_provider() -> str:
    """Resolve 'auto' to a concrete provider based on what's available."""
    if LLM_PROVIDER in ("openai", "local", "none"):
        return LLM_PROVIDER
    if LLM_BASE_URL and _server_reachable():
        return "openai"
    if os.path.exists(LLM_MODEL_PATH):
        return "local"
    return "none"


def _get_local():
    """Lazily load and cache the in-process GGUF model (CPU fallback)."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from llama_cpp import Llama
                _model = Llama(
                    model_path=LLM_MODEL_PATH,
                    n_ctx=LLM_N_CTX,
                    n_gpu_layers=-1,
                    verbose=False,
                )
    return _model


def available() -> bool:
    return _effective_provider() != "none"


def info() -> dict:
    prov = _effective_provider()
    if prov == "openai":
        return {"provider": "llama.cpp-server", "available": True,
                "backend": "gpu", "endpoint": LLM_BASE_URL}
    if prov == "local":
        return {"provider": "in-process", "available": True,
                "backend": "cpu", "model": os.path.basename(LLM_MODEL_PATH)}
    return {"provider": "none", "available": False}


def chat(system: str, user: str, max_tokens: int = 320, temperature: float = 0.3,
         timeout: int = 180) -> str | None:
    """Return the model's reply, or None on any failure (caller falls back to rules)."""
    prov = _effective_provider()
    try:
        if prov == "openai":
            import requests
            headers = {"Content-Type": "application/json"}
            if LLM_API_KEY:
                headers["Authorization"] = f"Bearer {LLM_API_KEY}"
            resp = requests.post(
                f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
                headers=headers,
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()

        if prov == "local":
            out = _get_local().create_chat_completion(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return out["choices"][0]["message"]["content"].strip()
    except Exception as e:  # noqa: BLE001 — never let the LLM break the endpoint
        print(f"[llm_client] generation failed ({prov}): {e}")
        return None
    return None
