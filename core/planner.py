import json
from typing import Optional
import config


class Planner:
    def __init__(self, llm_client):
        self.llm = llm_client

    def build_plan(self, goal: str) -> dict:
        prompt = f"""Kullanicinin hedefi: "{goal}"

Bir yazilim gelistirme ajani olarak bu hedefe ulasmak icin ADIM ADIM detayli bir plan olustur.
JSON formatinda cevap ver. JSON disinda hicbir sey yazma.

JSON semasi:
{{
  "proje_adi": "kisa-tire-ile-proje-adi",
  "aciklama": "1-2 cumle proje ozeti",
  "teknolojiler": ["python", "flask", vs],
  "ana_adimlar": [
    {{
      "no": 1,
      "adim": "Adim basligi",
      "detay": "Ne yapilacagi detaylari",
      "dosyalar": ["dosya1.py", "klasor/dosya2.js"],
      "test_gerekli": true/false
    }}
  ],
  "bagimliliklar": ["paket1", "paket2>=surum"],
  "test_stratejisi": "Test nasil yapilacak",
  "tahmini_iterasyon_sayisi": 8
}}

Yalnizca gecerli JSON dondur. Cift tirnak kullan. Ascii disi karakterler sorun degil."""

        raw = self.llm.generate(prompt, temperature=0.1, max_tokens=450, label="Adım adım plan tasarlanıyor")
        plan = self._parse_json(raw)
        if plan is None:
            plan = self._fallback_plan(goal)
        return plan

    def _parse_json(self, text: str) -> Optional[dict]:
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            candidate = text[start:end + 1]
            try:
                return json.loads(candidate)
            except Exception:
                pass
        try:
            return json.loads(text)
        except Exception:
            return None

    def _fallback_plan(self, goal: str) -> dict:
        words = goal.lower().replace(" ", "-")
        clean = "".join(c if c.isalnum() or c == "-" else "-" for c in words).strip("-")[:40] or "proje"
        return {
            "proje_adi": clean,
            "aciklama": f"Otonom olarak gelistirilen proje: {goal}",
            "teknolojiler": ["python"],
            "ana_adimlar": [
                {"no": 1, "adim": "Proje klasoru olustur", "detay": "workspace icinde proje klasoru olustur", "dosyalar": [], "test_gerekli": False},
                {"no": 2, "adim": "Gereksinimleri belirle", "detay": "Ihtiyac duyulan paketleri yaz", "dosyalar": ["requirements.txt"], "test_gerekli": False},
                {"no": 3, "adim": "Ana kodu yaz", "detay": "Uygulamanin ana dosyasini olustur", "dosyalar": ["app.py"], "test_gerekli": True},
                {"no": 4, "adim": "Bagimliliklari kur", "detay": "requirements.txt dosyasini kur", "dosyalar": [], "test_gerekli": False},
                {"no": 5, "adim": "Test et", "detay": "Kodu calistirip hatalari duzelt", "dosyalar": [], "test_gerekli": True},
            ],
            "bagimliliklar": [],
            "test_stratejisi": "Kodu dogrudan python ile calistir, ciktilari kontrol et",
            "tahmini_iterasyon_sayisi": 6,
        }
