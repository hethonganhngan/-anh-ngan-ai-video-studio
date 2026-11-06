# Mở Chrome riêng cho "Google Flow tự động" (provider flow_cdp, D21) với cổng CDP 9222 chỉ nghe 127.0.0.1.
#   powershell -ExecutionPolicy Bypass -File scripts\windows\start-flow-chrome.ps1
# Lần đầu: đăng nhập tài khoản Google có gói Flow trong cửa sổ này (phiên được lưu ở profile riêng).
# Chrome 136+ không cho bật CDP trên profile mặc định → bắt buộc dùng --user-data-dir riêng.
# Lưu ý: khi cổng 9222 mở, mọi chương trình trên máy này đều điều khiển được cửa sổ Chrome đó — chỉ dùng cho Flow.
. "$PSScriptRoot\common.ps1"
$Port = if ($env:FLOW_CDP_PORT) { $env:FLOW_CDP_PORT } else { "9222" }
$ProfileDir = "$Data\chrome-flow"
$Chrome = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
            "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
            "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Chrome) { throw "Không tìm thấy Google Chrome" }

try {
    Invoke-RestMethod "http://127.0.0.1:$Port/json/version" -TimeoutSec 2 | Out-Null
    Write-Host "Chrome Flow đã chạy (CDP 127.0.0.1:$Port)"
    exit 0
} catch {}

New-Item -ItemType Directory -Force $ProfileDir | Out-Null
Start-Process -FilePath $Chrome -ArgumentList @("--remote-debugging-port=$Port", "--remote-debugging-address=127.0.0.1",
    "--user-data-dir=`"$ProfileDir`"", "--no-first-run", "--no-default-browser-check", "https://flow.google.com/")
Write-Host "Đã mở Chrome Flow (profile $ProfileDir, CDP 127.0.0.1:$Port). Đăng nhập Flow nếu được hỏi, rồi để cửa sổ chạy nền."
