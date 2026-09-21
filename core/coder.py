import json
from pathlib import Path
from typing import Optional
import config


class Coder:
    def __init__(self, llm_client, fs_tool, python_tool):
        self.llm = llm_client
        self.fs = fs_tool
        self.python = python_tool

    def code_from_plan(self, step: dict, project_dir: str, context: str = "") -> list[dict]:
        proje_adi = step.get("adim", "")
        dosyalar = step.get("dosyalar", [])
        detay = step.get("detay", "")

        results = []
        for fname in dosyalar:
            full_path = str(Path(project_dir) / fname)
            content = self._generate_file(fname, detay, context, project_dir)
            if content:
                r = self.fs.write_file(full_path, content)
                results.append({"file": fname, "result": r})
            else:
                results.append({"file": fname, "result": {"success": False, "error": "Icerik uretilmedi"}})
        return results

    def _generate_file(self, filename: str, step_detail: str, context: str, project_dir: str) -> Optional[str]:
        prompt = f"""Bir yazilim gelistirme ajani olarak dosya kodu uret.

Proje klasoru: {project_dir}
Uretilecek dosya: {filename}
Adim detayi: {step_detail}

Ek baglam (onceki adimlardan bilgiler):
{context or "Yok"}

KURAL:
- Gecerli, calisir, temiz kod yaz
- Hata yonetimi (try/except) ekle
- logging veya print ile debug ciktilari ekle
- config, .env, sabitler icin ayrismis alanlar kullan
- Script ise if __name__ == "__main__": blogu ekle
- Fonksiyon, sinif ve degisken isimleri acik ve anlamli olsun
- Sadece dosya icerigini yaz, aciklama, markdown, ``` gibi dis seyler YOK.

Sadece kod icerigini dondur:"""
        result = self.llm.generate(prompt, temperature=0.2, label=f"'{filename}' dosyası kodlanıyor")
        result = self._clean_code_block(result)
        return result

    @staticmethod
    def _clean_code_block(text: str) -> str:
        if text is None:
            return ""
        t = text.strip()
        if t.startswith("```"):
            t = t[3:]
            first_line_end = t.find("\n")
            if first_line_end >= 0 and t[:first_line_end].strip().isalpha():
                t = t[first_line_end + 1:]
            else:
                t = t.lstrip("\n")
        if t.endswith("```"):
            t = t[:-3]
        return t.strip("\n") + "\n"

    def fix_code(self, file_path: str, original_code: str, error_info: dict, step_context: str) -> tuple[bool, str]:
        prompt = f"""Asagidaki Python dosyasinda bir hata var. Hatayi analiz edip DUZELTILMIS kodunu dondur.

Dosya: {file_path}
Hata turu: {error_info.get('error_type', 'Bilinmiyor')}
Hata mesaji: {error_info.get('error_message', 'Bilinmiyor')}
Hata satiri: {error_info.get('line', 'Bilinmiyor')}
Hata dosyasi: {error_info.get('file', 'Bilinmiyor')}

Kod:
```
{original_code}
```

Ek baglam:
{step_context}

KURAL:
- Tüm dosyayi, tam calisir halde dondur
- Sadece kodu yaz, aciklama ekleme
- Kodu ``` python blogu icine alma, sadece saf kodu dondur

DUZELTILMIS KOD:"""
        result = self.llm.generate(prompt, temperature=0.1, label="Hata analiz edilip düzeltiliyor")
        cleaned = self._clean_code_block(result)
        return (len(cleaned) > 10, cleaned)
