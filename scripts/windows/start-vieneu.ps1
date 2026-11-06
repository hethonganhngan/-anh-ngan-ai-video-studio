# Cài (lần đầu) và chạy VieNeu-TTS v3 Turbo — giọng nhân bản từ bản ghi âm chính chủ (provider vieneu_local, D23).
#   powershell -ExecutionPolicy Bypass -File scripts\windows\start-vieneu.ps1
# Chạy bằng CPU (ONNX), chỉ nghe 127.0.0.1:8200. Mã nguồn: github.com/pnnbao97/VieNeu-TTS (Apache-2.0), ghim bản v3.8.3.
# Lần đầu tải thư viện + mô hình (vài GB) nên mất vài phút.
. "$PSScriptRoot\common.ps1"
$Dir = "$Data\vieneu"
$Port = if ($env:VIENEU_PORT) { $env:VIENEU_PORT } else { "8200" }

if (-not (Test-Path "$Dir\.git")) {
    Write-Host "  tải VieNeu-TTS v3.8.3..."
    git clone --depth 1 --branch v3.8.3 https://github.com/pnnbao97/VieNeu-TTS.git $Dir
    if ($LASTEXITCODE -ne 0) { throw "Không tải được VieNeu-TTS" }
}
if (-not (Test-Path "$Dir\.venv\Scripts\python.exe")) {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "Cần cài uv: https://docs.astral.sh/uv/" }
    Write-Host "  cài thư viện VieNeu (CPU, lần đầu vài phút)..."
    Push-Location $Dir; cmd /c "uv sync > `"$Logs\vieneu-install.log`" 2>&1"; $ok = $LASTEXITCODE; Pop-Location
    if ($ok -ne 0) { throw "Cài VieNeu lỗi — xem $Logs\vieneu-install.log" }
}

$env:HOST = "127.0.0.1"; $env:PORT = $Port; $env:VIENEU_BACKEND = "onnx"
Start-Svc "vieneu" "$Dir\.venv\Scripts\python.exe" @("-m", "apps.openai_speech") $Dir
for ($i = 0; $i -lt 90; $i++) {   # lần đầu tải mô hình — chờ tối đa ~6 phút
    try { $h = Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 3; Write-Host "  vieneu sẵn sàng ($($h.backend))"; exit 0 } catch { Start-Sleep 4 }
}
Write-Host "  vieneu chưa sẵn sàng — xem $Logs\vieneu.err.log"
