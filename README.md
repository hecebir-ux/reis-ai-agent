# REIS AI AUTONOMOUS AGENT

Yerel Ollama uzerinde calisan, Windows 11 uyumlu otonom yazilim gelistirme ajani.

## REIS AI MAX

`start.bat` veya `python main.py` ile MAX ortamini acin. Eski v2 girisi: `python agent.py`.

Yeni katmanlar: SQLite bellek, model router, intent, gorev kuyrugu, guvenlik, local API, plugin iskeleti, self-debug.

```
python tests/test_reis_max.py
python tests/REIS_OTOMATIK_TEST.py
```


## Ozellikler

- Kendi kendine plan yapar
- Dosya ve klasor olusturur
- Terminal komutlari calistirir (python, pip, git, npm vb.)
- Kod yazar
- Test eder
- Hatalari analiz edip otomatik duzeltir
- Gorev bellegi tutar (JSON)
- Web arastirmasi yapar (beyaz listedeki resmi siteler)

## Kullanim

```
setup.bat    (ilk kez - paketleri kurar)
start.bat    (ajani baslatir)
```

Ajan acildiktan sonra ornek:

```
REIS AI > Telegram müzik botu yap
REIS AI > Flask ile todo app yap
REIS AI > Python'da fibonacci hesaplayici yaz ve test et
```

## Yapilandirma

`.env` dosyasindan ayarlanabilir:

- `OLLAMA_BASE_URL` : Ollama API adresi (varsayilan http://127.0.0.1:11434)
- `OLLAMA_MODEL`    : Kullanilacak model (varsayilan qwen2.5-coder)
- `MAX_ITERATIONS`  : Maksimum dongu sayisi
- `MAX_DEBUG_ATTEMPTS` : Her hata icin maksimum deneme

## Klasorler

```
REIS_AI_AGENT/
├── agent.py          - Ana giris noktasi
├── config.py         - Yapilandirma
├── core/
│   ├── planner.py    - Planlayici
│   ├── executor.py   - Yurutucu dongu
│   ├── coder.py      - Kod uretici
│   ├── tester.py     - Test motoru
│   ├── debugger.py   - Otomatik hata duzeltici
│   ├── memory.py     - Gorev bellegi (JSON)
│   └── llm_client.py - Ollama API istemcisi
├── tools/
│   ├── terminal.py   - Komut calistirici
│   ├── filesystem.py - Dosya islemleri
│   ├── python_tool.py - Python/pip yardimcisi
│   └── web_tool.py   - Web arastirma
├── workspace/        - Uretilen projeler burada
├── memory/           - Gorev gecmisi JSON
├── logs/             - Gunlukler
├── setup.bat         - Kurulum betigi
└── start.bat         - Baslatma betigi
```
