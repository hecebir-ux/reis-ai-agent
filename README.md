# REIS AI ULTRA

Yerel **Ollama** üzerinde çalışan, Windows 11 uyumlu, self-evolution’lı otonom ajan.

**Repo:** https://github.com/hecebir-ux/reis-ai-agent

## Hızlı başlat

```bat
setup.bat
start.bat
```

Arayüz: http://127.0.0.1:8765/

EXE: `build_app.bat` → `dist\REIS_AI\REIS_AI.exe`

Telegram: `.env` içine `TELEGRAM_BOT_TOKEN=...` → `start_telegram.bat` veya `REIS_AI.exe --telegram`

## ULTRA donanım

| Modül | Ne yapar |
|---|---|
| Self Diagnostics | Kod tabanı tarama |
| Self Healing | Hata → patch → test → retry (max 3) / rollback |
| Self Evolver | Backup → syntax → test → commit / rollback |
| Feature Builder | Eksik yetenek (örn. desktop organizer) |
| Optimizer + Benchmark | Performans ölç / gerilemede reddet |
| Reviewer | İkinci geçiş kod inceleme |
| Model Router | FAST / CODING / ANALYSIS / VISION |
| Web Research | Local-first, resmi docs |
| Knowledge Memory | SQLite problem→çözüm |
| Security + Safe Update | SAFE / CAUTION / DANGEROUS |
| Project Mapper + Task State | Harita + restart resume |
| Web Command Center | Premium UI |
| Telegram Bot | Doğal dil + /evolve |
| Windows EXE | PyInstaller paketi |

## Test

```bat
.venv\Scripts\python.exe tests\test_self_evolution.py
```

## Güvenlik

- `.env` asla commit edilmez
- Token / secret koda yazılmaz
- Sistem klasörleri yazmaya kapalı
