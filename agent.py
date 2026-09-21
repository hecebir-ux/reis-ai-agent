#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.chdir(str(BASE_DIR))

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from colorama import init, Fore, Style
init()

import config
from core.llm_client import OllamaClient
from core.executor import Executor
from core.memory import Memory
from core.turkish import polish_turkish


LOGO = f"""{Fore.CYAN}
 ██▀███  ▓█████  ██▓ ██▓    ▓█████
▓██ ▒ ██▒▓█   ▀ ▓██▒▓██▒    ▓█   ▀
▓██ ░▄█ ▒▒███   ▒██▒▒██░    ▒███
▒██▀▀█▄  ▒▓█  ▄ ░██░▒██░    ▒▓█  ▄
░██▓ ▒██▒░▒████▒░██░░██████▒░▒████▒
░ ▒▓ ░▒▓░░░ ▒░ ░░▓  ░ ▒░▓  ░░░ ▒░ ░
  ░▒ ░ ▒░ ░ ░  ░ ▒ ░░ ░ ▒  ░ ░ ░  ░
  ░░   ░    ░    ▒ ░  ░ ░      ░
   ░      ░  ░ ░      ░  ░   ░  ░
{Style.RESET_ALL}  {Fore.GREEN}AUTONOMOUS AGENT v2.0{Style.RESET_ALL}  •  {Fore.YELLOW}Dual-Model Ollama{Style.RESET_ALL}
"""

HELP_TEXT = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗
║              REIS AI — KOMUTLAR VE ÖZELLİKLER               ║
╠══════════════════════════════════════════════════════════════╣
║  {Fore.WHITE}[hedef yazın]{Fore.CYAN}     → Otomatik yazılım projesi oluştur         ║
║  {Fore.WHITE}[soru yazın]{Fore.CYAN}      → Yapay zeka ile sohbet et                 ║
║                                                              ║
║  {Fore.GREEN}devam{Fore.CYAN}             → Son projeye kaldığı yerden devam        ║
║  {Fore.GREEN}özet{Fore.CYAN}              → Sohbeti kısaca özetle                   ║
║  {Fore.GREEN}düzelt: metin{Fore.CYAN}     → Yazım ve cümle düzeltmesi               ║
║  {Fore.GREEN}son proje{Fore.CYAN}         → Son proje klasörünü aç                  ║
║                                                              ║
║  {Fore.YELLOW}!komut{Fore.CYAN}            → Terminal komutu çalıştır               ║
║                  örn: !ollama list                           ║
║                  örn: !dir workspace                         ║
║                                                              ║
║  {Fore.GREEN}workspace{Fore.CYAN}         → Proje klasörünü File Explorer'da aç    ║
║  {Fore.GREEN}status{Fore.CYAN}            → Model + bağlantı durumu                ║
║  {Fore.GREEN}models{Fore.CYAN}            → Mevcut Ollama modellerini listele       ║
║  {Fore.GREEN}sessions{Fore.CYAN}          → Son 5 projeyi listele                  ║
║  {Fore.GREEN}cls / clear{Fore.CYAN}       → Ekranı temizle                         ║
║  {Fore.GREEN}history{Fore.CYAN}           → Sohbet geçmişini göster                ║
║  {Fore.GREEN}reset{Fore.CYAN}             → Sohbet geçmişini temizle               ║
║  {Fore.GREEN}help{Fore.CYAN}              → Bu yardım ekranı                       ║
║  {Fore.RED}quit / exit{Fore.CYAN}       → Çıkış                                 ║
╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""


def print_header():
    print(LOGO)
    chat_m = config.OLLAMA_CHAT_MODEL
    code_m = config.OLLAMA_CODE_MODEL
    print(f"  {Fore.WHITE}Sohbet:{Style.RESET_ALL} {Fore.MAGENTA}{chat_m}{Style.RESET_ALL}  |  "
          f"{Fore.WHITE}Kod/Plan:{Style.RESET_ALL} {Fore.CYAN}{code_m}{Style.RESET_ALL}  |  "
          f"{Fore.WHITE}Workspace:{Style.RESET_ALL} {Fore.GREEN}{config.WORKSPACE_DIR}{Style.RESET_ALL}")
    print("-" * 70)


def step_label(kind):
    colors = {
        "plan":    (Fore.BLUE,    "PLAN"),
        "execute": (Fore.CYAN,    "ÇALIŞTIRILDI"),
        "code":    (Fore.GREEN,   "KOD"),
        "test":    (Fore.YELLOW,  "TEST"),
        "debug":   (Fore.RED,     "DÜZELT"),
        "setup":   (Fore.MAGENTA, "KURULUM"),
    }
    c, n = colors.get(kind, (Fore.WHITE, kind.upper()))
    return f"[{c}{n}{Style.RESET_ALL}]"


def ollama_wizard_startup():
    llm = OllamaClient()

    print(f"\n{Fore.WHITE}[1/3] Ollama API bağlantısı test ediliyor...{Style.RESET_ALL}")
    h = llm.health_check()
    if not h.get("ok"):
        print(f"  {Fore.RED}HATA: {h.get('error')}{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}Çözüm: Ollama App'i başlatın veya kurun: https://ollama.com/download{Style.RESET_ALL}")
        return None

    models = h.get("models", [])
    print(f"  {Fore.GREEN}OK{Style.RESET_ALL} — {len(models)} model mevcut: {', '.join(models)}")

    llm.bind_installed_models()

    # Sohbet modeli kontrolü
    print(f"\n{Fore.WHITE}[2/3] Sohbet modeli '{llm.chat_model}' kontrol ediliyor...{Style.RESET_ALL}")
    if "vision" in (llm.chat_model or "").lower() or not llm.resolve_name(llm.chat_model, allow_vision=False):
        print(f"  {Fore.YELLOW}Uyarı: uygun sohbet modeli yok, metin modeli aranıyor.{Style.RESET_ALL}")
        alt = llm.resolve_name("llama3.2", allow_vision=False)
        if not alt:
            for m in models:
                if "vision" in m.lower():
                    continue
                if any(k in m.lower() for k in ["llama", "qwen", "mistral", "gemma"]):
                    alt = m
                    break
        if alt:
            llm.chat_model = alt
            print(f"  {Fore.GREEN}Alternatif sohbet modeli: {alt}{Style.RESET_ALL}")
        else:
            print(f"  {Fore.RED}Metin sohbet modeli bulunamadı.{Style.RESET_ALL}")
    else:
        print(f"  {Fore.GREEN}OK{Style.RESET_ALL} — '{llm.chat_model}' hazır")

    print(f"     Kod modeli: {llm.model}")

    # Kod modeli kontrolü
    print(f"\n{Fore.WHITE}[3/3] Model ile hızlı test...{Style.RESET_ALL}")
    resp = llm.generate(
        "Kısa Türkçe selamlama yap ve 'REIS AI v2.0 hazır' yaz. Max 2 cümle.",
        temperature=0.1,
        max_tokens=60,
        label="Başlangıç testi",
        use_code_model=False,
    )
    if "LLM_HATA" in resp:
        print(f"  {Fore.YELLOW}Test yanıtı alınamadı: {resp[:100]}{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}Yine de devam ediliyor...{Style.RESET_ALL}")
    else:
        print(f"  {Fore.GREEN}Cevap:{Style.RESET_ALL} {resp.strip()}")

    return llm


# ─── AKILLI INTENT DETECTION (LLM çağrısı YOK — anlık karar) ───────────────

# Yazılım projesi yapma fiilleri (Türkçe)
_BUILD_VERBS = {
    "yap", "yaz", "kodla", "üret", "uret", "geliştir", "gelistir",
    "oluştur", "olustur", "kur", "hazırla", "hazirla", "tasarla",
    "create", "build", "make", "develop", "code", "generate",
    "ekle", "implement", "deploy", "çalıştır", "calistir",
}

# Sohbet / soru göstergeleri
_CHAT_WORDS = {
    "kimsin", "tanıt", "tanit", "nasılsın", "nasilsin",
    "merhaba", "selam", "naber", "ne haber", "iyi misin",
    "nedir", "ne demek", "nasıl", "nasil", "anlat", "açıkla", "acikla",
    "kimdir", "farkı", "farki", "espri", "şaka", "saka",
    "fikir", "öneri", "oneri", "tavsiye", "neden", "niye",
    "ne düşünüyorsun", "ne dusunuyorsun", "bana anlat",
    "ne zaman", "ne kadar", "kaç", "kac", "hangi",
    "hello", "hi", "who are you", "what is", "explain",
    "günaydın", "gunaydin", "iyi geceler", "iyi günler", "teşekkür",
    "tesekkur", "sağol", "sagol", "eyvallah", "tamam", "anladım", "anladim",
    "neler", "yapabiliyorsun", "yapabiliyosun", "özellik", "ozellik",
}

_CONTINUE_PHRASES = (
    "devam", "devam et", "devam edelim", "kaldığın yerden", "kaldigin yerden",
    "son projeye devam", "dün yaptığımız", "dun yaptigimiz", "aynı işe devam",
)


def classify_intent(goal: str) -> str:
    """
    'CHAT' veya 'PROJECT' döndürür — LLM çağrısı olmadan anlık karar.
    """
    raw = (goal or "").strip().lower()
    words = set(raw.replace("?", " ").replace("!", " ").replace(":", " ").split())
    is_question = goal.strip().endswith("?")

    has_chat_word = bool(words & _CHAT_WORDS)
    has_build_verb = bool(words & _BUILD_VERBS)

    if raw.startswith("düzelt:") or raw.startswith("duzelt:"):
        return "CHAT"
    if raw in {"özet", "ozet", "özetle", "ozetle"}:
        return "CHAT"
    if raw in _CONTINUE_PHRASES or raw.startswith("devam"):
        return "CONTINUE"
    if is_question and not has_build_verb:
        return "CHAT"
    if has_chat_word and not has_build_verb:
        return "CHAT"
    if has_build_verb and len(words) >= 2:
        return "PROJECT"
    if len(words) <= 2:
        return "CHAT"
    return "CHAT"


# ─── İNTERAKTİF DÖNGÜ ───────────────────────────────────────────────────────

def interactive_loop(llm: OllamaClient):
    memory = Memory()
    executor = Executor(llm)
    chat_history: list[dict] = []   # Sohbet geçmişi (çok turlu hafıza)

    SYSTEM_CHAT = (
        "Sen REIS AI'sin. Windows 11 üzerinde yerel Ollama ile çalışan, "
        "son derece zeki ve samimi bir yapay zeka asistanısın. "
        "Türkçe konuş, kısa ve öz cevap ver. "
        "Eğer kullanıcı bir yazılım projesi yapmak isterse "
        "'Tabii, sadece hedefini yaz, projeyi otomatik kodlar ve test ederim.' de."
    )

    def on_memory_step(session_id, kind, msg, detail):
        print(f"  {step_label(kind)} {msg[:140]}", flush=True)

    print(f"\n{Fore.GREEN}{'═' * 70}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}Hazır!{Style.RESET_ALL} Hedef veya soru yazın.  {Fore.YELLOW}help{Style.RESET_ALL} → komutlar  {Fore.YELLOW}quit{Style.RESET_ALL} → çıkış")
    print(f"{Fore.GREEN}{'═' * 70}{Style.RESET_ALL}\n")

    while True:
        try:
            goal = input(f"{Fore.MAGENTA}REIS AI >{Style.RESET_ALL} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Fore.YELLOW}Güle güle!{Style.RESET_ALL}")
            break

        if not goal:
            continue

        # ── Çıkış ──────────────────────────────────────────────────────────
        if goal.lower() in {"quit", "exit", "q", "bye", "çıkış", "cikis"}:
            print(f"{Fore.YELLOW}Güle güle!{Style.RESET_ALL}")
            break

        # ── Yardım ─────────────────────────────────────────────────────────
        if goal.lower() in {"help", "yardım", "yardim", "?"}:
            print(HELP_TEXT)
            continue

        # ── Ekran temizle ───────────────────────────────────────────────────
        if goal.lower() in {"cls", "clear", "temizle"}:
            os.system("cls" if os.name == "nt" else "clear")
            print_header()
            continue

        # ── Workspace aç ────────────────────────────────────────────────────
        if goal.lower() in {"workspace", "ws", "klasör", "klasor"}:
            ws = str(config.WORKSPACE_DIR)
            print(f"  {Fore.CYAN}Workspace: {ws}{Style.RESET_ALL}")
            try:
                subprocess.Popen(["explorer", ws])
                print(f"  {Fore.GREEN}File Explorer açıldı!{Style.RESET_ALL}")
            except Exception as e:
                print(f"  {Fore.RED}Açılamadı: {e}{Style.RESET_ALL}")
            continue

        # ── Status ──────────────────────────────────────────────────────────
        if goal.lower() in {"status", "durum"}:
            h = llm.health_check()
            state = f"{Fore.GREEN}OK{Style.RESET_ALL}" if h.get("ok") else f"{Fore.RED}HATA{Style.RESET_ALL}"
            print(f"  Ollama: {state}  |  Sohbet: {Fore.MAGENTA}{llm.chat_model}{Style.RESET_ALL}  |  Kod: {Fore.CYAN}{llm.model}{Style.RESET_ALL}")
            continue

        # ── Models ──────────────────────────────────────────────────────────
        if goal.lower() in {"models", "modeller", "model list"}:
            h = llm.health_check()
            if h.get("ok"):
                print(f"\n  {Fore.CYAN}Mevcut Ollama Modelleri:{Style.RESET_ALL}")
                for i, m in enumerate(h.get("models", []), 1):
                    marker = " ◄ aktif" if m.startswith(llm.chat_model.split(":")[0]) else ""
                    print(f"  {i}. {Fore.WHITE}{m}{Style.RESET_ALL}{Fore.YELLOW}{marker}{Style.RESET_ALL}")
            else:
                print(f"  {Fore.RED}Ollama bağlantısı yok{Style.RESET_ALL}")
            continue

        # ── Sessions ────────────────────────────────────────────────────────
        if goal.lower() in {"sessions", "oturumlar", "projeler"}:
            sessions = memory.data.get("sessions", [])[-5:]
            if not sessions:
                print(f"  {Fore.YELLOW}Henüz proje yok.{Style.RESET_ALL}")
            else:
                print(f"\n  {Fore.CYAN}Son 5 Proje:{Style.RESET_ALL}")
                for s in sessions:
                    st = s.get("status", "?")
                    col = Fore.GREEN if st == "success" else (Fore.YELLOW if st == "partial" else Fore.RED)
                    print(f"  [{col}{st.upper():8}{Style.RESET_ALL}] {s.get('goal','')[:55]}  {Fore.WHITE}{s.get('id','')}{Style.RESET_ALL}")
            print()
            continue

        # ── Sohbet geçmişi ──────────────────────────────────────────────────
        if goal.lower() in {"history", "gecmis", "geçmiş"}:
            if not chat_history:
                print(f"  {Fore.YELLOW}Sohbet geçmişi boş.{Style.RESET_ALL}")
            else:
                print(f"\n  {Fore.CYAN}Sohbet Geçmişi ({len(chat_history)} mesaj):{Style.RESET_ALL}")
                for i, m in enumerate(chat_history, 1):
                    role_color = Fore.MAGENTA if m["role"] == "user" else Fore.GREEN
                    role_label = "Sen" if m["role"] == "user" else "REIS"
                    content = m["content"][:80] + ("..." if len(m["content"]) > 80 else "")
                    print(f"  {role_color}[{role_label}]{Style.RESET_ALL} {content}")
            print()
            continue

        # ── Geçmiş sıfırla ──────────────────────────────────────────────────
        if goal.lower() in {"reset", "sıfırla", "sifirla", "yeni sohbet"}:
            chat_history.clear()
            print(f"  {Fore.GREEN}Sohbet geçmişi temizlendi.{Style.RESET_ALL}")
            continue

        # ── Terminal komutu (!komut) ─────────────────────────────────────────
        if goal.startswith("!"):
            cmd = goal[1:].strip()
            if not cmd:
                print(f"  {Fore.YELLOW}Kullanım: !komut  (örn: !ollama list){Style.RESET_ALL}")
                continue
            print(f"  {Fore.YELLOW}>> Komut çalıştırılıyor: {cmd}{Style.RESET_ALL}")
            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True,
                    timeout=30, encoding="utf-8", errors="replace"
                )
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(f"{Fore.RED}{result.stderr}{Style.RESET_ALL}")
                if result.returncode != 0:
                    print(f"  {Fore.YELLOW}Çıkış kodu: {result.returncode}{Style.RESET_ALL}")
            except subprocess.TimeoutExpired:
                print(f"  {Fore.RED}Komut zaman aşımına uğradı (30 sn){Style.RESET_ALL}")
            except Exception as e:
                print(f"  {Fore.RED}Hata: {e}{Style.RESET_ALL}")
            continue

        # ─── AKILLI KARAR: SOHBET mi PROJE mi? ──────────────────────────────
        intent = classify_intent(goal)

        # ── SOHBET MODU: Hızlı streaming (llama3.2) ─────────────────────────
        if intent == "CHAT":
            # Geçmişe ekle (max 10 tur = 20 mesaj)
            chat_history.append({"role": "user", "content": goal})
            if len(chat_history) > 20:
                chat_history = chat_history[-20:]

            messages = [{"role": "system", "content": SYSTEM_CHAT}] + chat_history

            print(f"\n{Fore.GREEN}REIS AI:{Style.RESET_ALL} ", end="", flush=True)
            response = llm.chat_stream(messages, max_tokens=400, use_code_model=False)
            print("\n", flush=True)

            if response and not response.startswith("[LLM_HATA"):
                chat_history.append({"role": "assistant", "content": response})
            continue

        # ── PROJE MODU: Executor (qwen2.5-coder) ────────────────────────────
        print(f"\n{Fore.CYAN}{'═' * 70}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}🚀 PROJE BAŞLADI: {goal}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'═' * 70}{Style.RESET_ALL}\n")

        original_add_step = memory.add_step

        def hooked_add_step(sid, kind, msg, detail=None):
            original_add_step(sid, kind, msg, detail)
            on_memory_step(sid, kind, msg, detail)

        memory.add_step = hooked_add_step

        try:
            result = executor.run(goal, memory)
        except Exception as e:
            print(f"{Fore.RED}Ajan hatası: {type(e).__name__}: {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            continue
        finally:
            memory.add_step = original_add_step

        sid = result.get("session_id", "?")
        status = result.get("status", "?")
        pdir = result.get("project_dir", "")

        color = Fore.GREEN if status == "success" else (Fore.YELLOW if status == "partial" else Fore.RED)
        icon = "✅" if status == "success" else ("⚠️" if status == "partial" else "❌")

        print(f"\n{color}{'═' * 70}{Style.RESET_ALL}")
        print(f"{color}{icon} SONUÇ: {status.upper()}{Style.RESET_ALL}  │  Session: {Fore.WHITE}{sid}{Style.RESET_ALL}")
        if pdir:
            print(f"  {Fore.WHITE}Proje klasörü:{Style.RESET_ALL} {Fore.CYAN}{pdir}{Style.RESET_ALL}")
            # Başarılıysa otomatik aç
            if status == "success":
                try:
                    subprocess.Popen(["explorer", str(pdir)])
                    print(f"  {Fore.GREEN}→ File Explorer'da açıldı!{Style.RESET_ALL}")
                except Exception:
                    pass
        ft = result.get("final_test") or {}
        if ft.get("stdout"):
            print(f"\n  {Fore.WHITE}Çıktı (son 400 karakter):{Style.RESET_ALL}")
            print(f"  {ft['stdout'][-400:]}")
        if ft.get("stderr") and not ft.get("success"):
            print(f"\n  {Fore.RED}Hata çıktısı:{Style.RESET_ALL}")
            print(f"  {ft['stderr'][-300:]}")
        print(f"\n  {Fore.WHITE}Detaylı log:{Style.RESET_ALL} memory/ klasörüne bakın")
        print(f"{color}{'═' * 70}{Style.RESET_ALL}\n")


def main():
    print_header()
    try:
        llm = ollama_wizard_startup()
    except Exception as e:
        print(f"\n{Fore.RED}[KURULUM HATASI] {type(e).__name__}: {e}{Style.RESET_ALL}")
        llm = None

    if llm is None:
        print(f"\n{Fore.RED}Ollama hazır değil. Önerilen adımlar:{Style.RESET_ALL}")
        print(f"  1. {Fore.YELLOW}Ollama App{Style.RESET_ALL} çalışıyor mu? (Windows arama çubuğuna Ollama yazın)")
        print(f"  2. Model indirme: {Fore.CYAN}ollama pull {config.OLLAMA_CHAT_MODEL}{Style.RESET_ALL}")
        print(f"  3. setup.bat'ı tekrar çalıştırın")
        print()
        print(f"{Fore.YELLOW}Yine de sınırlı modda başlatılıyor...{Style.RESET_ALL}")
        import time
        try:
            for i in range(3, 0, -1):
                print(f"  {i}...", end="", flush=True)
                time.sleep(1)
            print()
        except (EOFError, KeyboardInterrupt):
            print()

    try:
        interactive_loop(llm if llm is not None else OllamaClient())
    except Exception as e:
        print(f"\n{Fore.RED}[KRİTİK HATA] {type(e).__name__}: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        print()
        try:
            input("Çıkmak için Enter basın...")
        except EOFError:
            pass


if __name__ == "__main__":
    # start.bat burayı çağırır → REIS AI MAX + tüm Self-Evolution sistemleri
    from main import main as max_main

    max_main()
