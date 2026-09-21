import os
import sys
import platform
import json
import subprocess
import requests
from pathlib import Path

def get_system_info():
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "python_version": sys.version,
        "current_dir": str(Path(os.getcwd()).absolute()),
        "installed_packages": subprocess.check_output([sys.executable, "-m", "pip", "list"]).decode('utf-8')
    }

def check_ollama():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        if response.status_code == 200:
            return {"status": "online", "models": response.json().get("models", [])}
        return {"status": "error", "code": response.status_code}
    except Exception as e:
        return {"status": "offline", "error": str(e)}

def scan_files(root_dir):
    project_structure = []
    exclude_dirs = {'.git', '__pycache__', '.venv', 'venv', '.idea', '.vscode', 'logs', 'tests', '.ipynb_checkpoints'}
    exclude_exts = {'.exe', '.dll', '.pyc', '.png', '.jpg', '.jpeg', '.gif', '.mp4', '.zip', '.tar', '.gz', '.7z', '.pyo'}

    for root, dirs, files in os.walk(root_dir):
        # Klasörleri filtrele
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            file_path = Path(root) / file
            relative_path = file_path.relative_to(root_dir)
            
            file_info = {
                "path": str(relative_path),
                "size": file_path.stat().st_size,
                "extension": file_path.suffix
            }

            # Kod içeriğini oku (Analiz için)
            if file_path.suffix in ['.py', '.json', '.md', '.txt', '.toml', '.yaml', '.yml']:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        # Context limitini aşmamak için ilk 10.000 karakteri al
                        content = f.read(10000)
                        file_info["content"] = content
                except Exception as e:
                    file_info["content_error"] = str(e)
            
            project_structure.append(file_info)
            
    return project_structure

def main():
    print("--- REIS AI SCANNER: ANALİZ BAŞLATILDI ---")
    report = {
        "system": get_system_info(),
        "ollama": check_ollama(),
        "project_files": scan_files(".")
    }
    
    with open("reis_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print("--- ANALİZ TAMAMLANDI ---")
    print("--- DOSYA OLUŞTURULDU: reis_report.json ---")
    print("LÜTFEN 'reis_report.json' İÇERİĞİNİ BURAYA YAPIŞTIRIN.")

if __name__ == "__main__":
    main()
