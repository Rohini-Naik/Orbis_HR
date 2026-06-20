"""Compatibility helpers for Hugging Face InferenceClient calls.

Provides wrappers that try multiple call signatures to support different
versions of `huggingface_hub`.
"""
from typing import Any, Iterable


def text_generation(client: Any, model: str, prompt: str, params: dict | None = None) -> Any:
    params = params or {}
    params = params or {}

    # Prefer explicit method detection to avoid AttributeErrors from differing client versions
    last_exc: Exception | None = None

    # Try InferenceClient.text_generation if available
    if hasattr(client, "text_generation"):
        try:
            return client.text_generation(model=model, inputs=prompt, params=params)
        except TypeError:
            try:
                return client.text_generation(model, prompt, parameters=params)
            except Exception as e:
                last_exc = e
        except Exception as e:
            last_exc = e

    # Try InferenceClient.generate if available
    if hasattr(client, "generate"):
        try:
            return client.generate(model=model, inputs=prompt, parameters=params)
        except TypeError:
            try:
                return client.generate(model, prompt, parameters=params)
            except Exception as e:
                last_exc = e
        except Exception as e:
            last_exc = e

    # As a last resort, attempt the HF HTTP Inference endpoint directly. This may fail
    # if DNS/network is unavailable — surface a clearer error in that case.
    try:
        import os
        import requests

        token = os.environ.get("HUGGINGFACE_API_KEY")
        if not token:
            # if no token available, raise the original exception
            if last_exc:
                raise last_exc
            raise RuntimeError("HUGGINGFACE_API_KEY not set for HTTP fallback")

        url = f"https://api-inference.huggingface.co/models/{model}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"inputs": prompt, "parameters": params}
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return r.text
    except requests.exceptions.RequestException as net_err:
        # Network/DNS/proxy issues — give a clear message
        raise RuntimeError(
            "Failed to reach Hugging Face Inference API (network/DNS/proxy issue). "
            "Check network connectivity, DNS resolution for api-inference.huggingface.co, and any proxy settings. "
            f"Underlying error: {net_err}"
        ) from net_err
    except Exception:
        if last_exc:
            raise last_exc
        raise


def embeddings_call(client: Any, model: str, inputs: Iterable[str]) -> list[list[float]]:
    # Try several signatures for embeddings
    trials = []
    trials.append(lambda: client.embeddings(model=model, inputs=inputs))
    trials.append(lambda: client.embeddings(model=model, input=inputs))
    trials.append(lambda: client.embeddings(model, inputs=inputs))
    trials.append(lambda: client.embeddings(model, input=inputs))

    last_exc = None
    for fn in trials:
        try:
            return fn()
        except Exception as e:
            last_exc = e
            continue
    # Fallback to HTTP inference endpoint
    try:
        import os
        import requests

        token = os.environ.get("HUGGINGFACE_API_KEY")
        if not token:
            raise last_exc

        url = f"https://api-inference.huggingface.co/models/{model}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"inputs": list(inputs)}
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data
    except Exception:
        raise last_exc
