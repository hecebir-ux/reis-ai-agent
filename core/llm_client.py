import sys
import json
import time
import requests
import config


class OllamaClient:
    """
    Dual-model Ollama istemcisi:
      - self.model       → genel (kod/plan) → config.OLLAMA_CODE_MODEL
      - self.chat_model  → sohbet (hızlı)   → config.OLLAMA_CHAT_MODEL
    """

    def __init__(
        self,
        base_url: str = None,
        model: str = None,
        chat_model: str = None,
        timeout: int = None,
        temperature: float = None,
        ctx_window: int = None,
    ):
        self.base_url = base_url or config.OLLAMA_BASE_URL
        self.model = model or config.OLLAMA_CODE_MODEL      # Kod/Plan modeli
        self.chat_model = chat_model or config.OLLAMA_CHAT_MODEL  # Sohbet modeli
        self.timeout = timeout or config.OLLAMA_TIMEOUT
        self.temperature = temperature if temperature is not None else config.OLLAMA_TEMPERATURE
        self.ctx_window = ctx_window or config.OLLAMA_CTX_WINDOW
        self.session = requests.Session()
        self.max_retries = getattr(config, "OLLAMA_MAX_RETRIES", 2)

    # ─── Sağlık / model kontrolü ────────────────────────────────────────────

    def health_check(self) -> dict:
        try:
            r = self.session.get(f"{self.base_url}/api/tags", timeout=10)
            if r.status_code == 200:
                data = r.json()
                models = [m["name"] for m in data.get("models", [])]
                return {"ok": True, "models": models, "base_url": self.base_url}
            return {"ok": False, "error": f"HTTP {r.status_code}"}
        except requests.RequestException as e:
            return {"ok": False, "error": f"Baglanti hatasi: {e}"}

    def model_available(self, model_name: str = None) -> bool:
        return self.resolve_name(model_name or self.model, allow_vision=True) is not None

    def resolve_name(self, wanted: str, allow_vision: bool = False) -> str | None:
        h = self.health_check()
        if not h.get("ok"):
            return None
        models = h.get("models", []) or []
        w = (wanted or "").lower().strip()
        if not w:
            return None
        base = w.split(":")[0]
        exact = []
        family = []
        for m in models:
            ml = m.lower()
            if (not allow_vision) and "vision" in ml:
                continue
            mbase = ml.split(":")[0]
            if ml == w or ml == f"{base}:latest":
                exact.append(m)
            elif mbase == base:
                family.append(m)
        if exact:
            return exact[0]
        if family:
            return family[0]
        return None

    def bind_installed_models(self) -> None:
        chat = self.resolve_name(self.chat_model, allow_vision=False) or self.resolve_name("llama3.2", allow_vision=False)
        code = self.resolve_name(self.model, allow_vision=False) or self.resolve_name("qwen2.5-coder", allow_vision=False)
        if chat:
            self.chat_model = chat
        if code:
            self.model = code

    # ─── İlerleme göstergesi (spinner) ──────────────────────────────────────

    def _run_with_spinner(self, func, label="Model yanıt üretiyor"):
        import threading
        stop_event = threading.Event()
        start = time.time()

        print(f"  \033[33m>> {label}...\033[0m", end="", flush=True)

        def progress_dots():
            while not stop_event.is_set():
                time.sleep(2.0)
                if not stop_event.is_set():
                    sys.stdout.write(".")
                    sys.stdout.flush()

        t = threading.Thread(target=progress_dots, daemon=True)
        t.start()
        try:
            res = func()
            elapsed = int(time.time() - start)
            print(f" \033[32m[{elapsed}sn]\033[0m", flush=True)
            return res
        except Exception:
            elapsed = int(time.time() - start)
            print(f" \033[31m[Hata - {elapsed}sn]\033[0m", flush=True)
            raise
        finally:
            stop_event.set()
            t.join(timeout=0.5)

    # ─── generate() — kod/plan için (qwen2.5-coder) ─────────────────────────

    def generate(
        self,
        prompt: str,
        system: str = None,
        temperature: float = None,
        max_tokens: int = None,
        label: str = "Model yanıt üretiyor",
        use_code_model: bool = True,   # Varsayılan: kod modeli kullan
    ) -> str:
        model_to_use = self.model if use_code_model else self.chat_model
        payload = {
            "model": model_to_use,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "num_ctx": self.ctx_window,
            },
        }
        if system:
            payload["system"] = system
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        def _do_post():
            from core.metrics import metrics

            last_err = None
            for attempt in range(self.max_retries + 1):
                t0 = time.perf_counter()
                try:
                    r = self.session.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                        timeout=self.timeout,
                    )
                    r.raise_for_status()
                    data = r.json()
                    metrics.record_ollama(time.perf_counter() - t0)
                    return data.get("response", "")
                except requests.RequestException as e:
                    metrics.record_retry()
                    metrics.record_error()
                    last_err = e
                    time.sleep(min(2 ** attempt, 4))
            raise last_err

        try:
            return self._run_with_spinner(_do_post, label)
        except requests.RequestException as e:
            fallback = self._fallback_model(model_to_use)
            if fallback and fallback != model_to_use:
                payload["model"] = fallback
                try:
                    return self._run_with_spinner(_do_post, f"{label} (fallback)")
                except Exception:
                    pass
            return f"[LLM_HATA: {type(e).__name__}: {e}]"
        except Exception as e:
            return f"[LLM_HATA: {type(e).__name__}: {e}]"

    def _fallback_model(self, failed: str) -> str | None:
        failed_l = (failed or "").lower()
        order = [
            getattr(config, "OLLAMA_CHAT_MODEL", "llama3.2"),
            getattr(config, "OLLAMA_FAST_MODEL", "llama3.2"),
            "llama3.2:latest",
            "llama3.2",
            self.chat_model,
            self.model,
        ]
        for m in order:
            if not m:
                continue
            if m.lower() == failed_l:
                continue
            if "vision" in m.lower():
                continue
            return m
        return None

    # ─── chat() — senkron (yavaş, nadiren kullanılır) ───────────────────────

    def chat(self, messages: list[dict], temperature: float = None, max_tokens: int = None, use_code_model: bool = False) -> str:
        model_to_use = self.model if use_code_model else self.chat_model
        payload = {
            "model": model_to_use,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "num_ctx": self.ctx_window,
            },
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        try:
            from core.metrics import metrics

            t0 = time.perf_counter()
            r = self.session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json()
            metrics.record_ollama(time.perf_counter() - t0)
            msg = data.get("message", {})
            return msg.get("content", "")
        except requests.RequestException as e:
            from core.metrics import metrics

            metrics.record_error()
            return f"[LLM_HATA: {type(e).__name__}: {e}]"
        except Exception as e:
            from core.metrics import metrics

            metrics.record_error()
            return f"[LLM_HATA: {type(e).__name__}: {e}]"

    # ─── chat_stream() — sohbet (think kapalı, Türkçe temizleme) ────────────

    def chat_stream(
        self,
        messages: list[dict],
        temperature: float = None,
        max_tokens: int = None,
        on_token=None,
        use_code_model: bool = False,
        think: bool = False,
    ) -> str:
        from core.turkish import StreamThinkFilter, polish_turkish

        model_to_use = self.model if use_code_model else self.chat_model
        payload = {
            "model": model_to_use,
            "messages": messages,
            "stream": True,
            "think": bool(think),
            "options": {
                "temperature": temperature if temperature is not None else 0.35,
                "num_ctx": self.ctx_window,
            },
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        filt = StreamThinkFilter()
        full_chunks: list[str] = []

        def emit(raw: str) -> None:
            visible = filt.feed(raw)
            if not visible:
                return
            full_chunks.append(visible)
            if on_token:
                on_token(visible)
            else:
                sys.stdout.write(visible)
                sys.stdout.flush()

        def consume(resp) -> None:
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except Exception:
                    continue
                token = (chunk.get("message", {}) or {}).get("content", "") or ""
                if token:
                    emit(token)
                if chunk.get("done", False):
                    break

        try:
            r = self.session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=self.timeout,
            )
            r.raise_for_status()
            consume(r)
            tail = filt.flush()
            if tail:
                full_chunks.append(tail)
                if on_token:
                    on_token(tail)
                else:
                    sys.stdout.write(tail)
                    sys.stdout.flush()
            return polish_turkish("".join(full_chunks))
        except Exception as e:
            err = f"[LLM_HATA: {type(e).__name__}: {e}]"
            fallback = self._fallback_model(model_to_use)
            if fallback and fallback != model_to_use:
                payload["model"] = fallback
                try:
                    r = self.session.post(
                        f"{self.base_url}/api/chat",
                        json=payload,
                        stream=True,
                        timeout=self.timeout,
                    )
                    r.raise_for_status()
                    consume(r)
                    if full_chunks:
                        return polish_turkish("".join(full_chunks) + filt.flush())
                except Exception:
                    pass
            print(f"\n{err}", flush=True)
            return err

    # ─── generate_stream() — kod streaming (nadiren) ────────────────────────

    def generate_stream(
        self,
        prompt: str,
        system: str = None,
        temperature: float = None,
        max_tokens: int = None,
        on_token=None,
        use_code_model: bool = True,
    ) -> str:
        model_to_use = self.model if use_code_model else self.chat_model
        payload = {
            "model": model_to_use,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "num_ctx": self.ctx_window,
            },
        }
        if system:
            payload["system"] = system
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        full_chunks = []
        try:
            r = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=True,
                timeout=self.timeout,
            )
            r.raise_for_status()
            for line in r.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                    except Exception:
                        continue
                    token = chunk.get("response", "")
                    if token:
                        full_chunks.append(token)
                        if on_token:
                            on_token(token)
                        else:
                            sys.stdout.write(token)
                            sys.stdout.flush()
                    if chunk.get("done", False):
                        break
            return "".join(full_chunks)
        except Exception as e:
            err = f"\n[LLM_HATA: {type(e).__name__}: {e}]"
            print(err, flush=True)
            return "".join(full_chunks)
