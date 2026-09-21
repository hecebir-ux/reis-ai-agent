# REIS AI Agent - Masaustune Kopyala (PowerShell ile kesin calisan)
param([switch]$Auto)

$ErrorActionPreference = "Stop"

$Src  = Split-Path -Parent $MyInvocation.MyCommand.Path
$Name = Split-Path -Leaf $Src
$Dst  = Join-Path ([Environment]::GetFolderPath("Desktop")) $Name

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  REIS AI Agent  ->  Masaustune Kopyalama" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Kaynak: $Src" -ForegroundColor Gray
Write-Host "Hedef : $Dst" -ForegroundColor Gray
Write-Host ""

if (Test-Path $Dst) {
    Write-Host "Dikkat: Hedef klasor zaten var, SILINIYOR..." -ForegroundColor Yellow
    Remove-Item -LiteralPath $Dst -Recurse -Force
    Start-Sleep -Milliseconds 500
}

# Boyut gostermek icin
$totalBytes = (Get-ChildItem -LiteralPath $Src -Recurse -File | Measure-Object -Property Length -Sum).Sum
$totalMB = [math]::Round($totalBytes / 1MB, 1)
Write-Host "Toplam veri: $totalMB MB  (~$([math]::Round($totalMB/1024,2)) GB)" -ForegroundColor White
Write-Host ""

# Kopyalama - GUI progress olmasin diye Copy-Item
Write-Host "Kopyalama basladi... Lutfen bekleyin (1-3 dakika)" -ForegroundColor Yellow
Copy-Item -LiteralPath $Src -Destination $Dst -Recurse -Force
Write-Host ""

# Dogrulama
if ((Test-Path $(Join-Path $Dst "start.bat")) -and (Test-Path $(Join-Path $Dst "setup.bat")) -and (Test-Path $(Join-Path $Dst "agent.py"))) {
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host "  BASARILI! Klasor Masaustune kopyalandi." -ForegroundColor Green
    Write-Host "  Yeni konum: $Dst" -ForegroundColor Green
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Siradaki adimlar:" -ForegroundColor White
    Write-Host "  1. Asagidaki klasorden setup.bat dosyasina cift tikla" -ForegroundColor Cyan
    Write-Host "  2. Kurulum bitince start.bat dosyasina cift tikla" -ForegroundColor Cyan
    Write-Host ""
    explorer $Dst
} else {
    Write-Host "HATA: Bazi kritik dosyalar eksik." -ForegroundColor Red
    Write-Host "Manuel yontem kullan:" -ForegroundColor Yellow
    Write-Host "  1. $Src klasorune sag tik -> Kopyala"
    Write-Host "  2. Masaustu bos alana sag tik -> Yapistir"
    exit 1
}

if (-not $Auto) {
    Write-Host ""
    Read-Host "Cikmak icin Enter'a basin"
}
exit 0
