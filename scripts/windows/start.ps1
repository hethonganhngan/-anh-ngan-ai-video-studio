# Bật toàn bộ Ánh Ngân AI Video Studio trên Windows (không Docker).
#   powershell -ExecutionPolicy Bypass -File scripts\windows\start.ps1
# Dữ liệu (DB, media, backup, log) ở ANNGAN_DATA_DIR (mặc định D:\AnhNganStudio).
. "$PSScriptRoot\common.ps1"
$WebPort = if ($env:WEB_PORT) { $env:WEB_PORT } else { "3001" }

Write-Host "Ánh Ngân AI Video Studio — khởi động"

# 1. PostgreSQL (pg_ctl tự chạy nền, không cần PID riêng)
& "$PgBin\pg_ctl.exe" -D "$Data\pgdata" status *> $null
if ($LASTEXITCODE -ne 0) {
    # Tiến trình tách rời, chỉ chờ pg_ctl (không chờ postgres con — nếu không lệnh sẽ treo vĩnh viễn)
    $pg = Start-Process -FilePath "$PgBin\pg_ctl.exe" -WindowStyle Hidden -PassThru `
        -ArgumentList @("-D", "`"$Data\pgdata`"", "-l", "`"$Logs\postgres.log`"", "-o", "`"-p 5432 -c listen_addresses=localhost`"", "-w", "start")
    $pg.WaitForExit()
    if ($pg.ExitCode -ne 0) { throw "Không bật được PostgreSQL — xem $Logs\postgres.log" }
    Write-Host "  postgres đã bật"
} else { Write-Host "  postgres đang chạy" }

# 2. Redis (broker Celery + rate limit)
Start-Svc "redis" "$Data\redis\redis-server.exe" @("--port", "6379", "--bind", "127.0.0.1", "--appendonly", "yes", "--dir", "$Data/redisdata") "$Data\redis"

# 3. Migration (idempotent)
Push-Location "$Root\services\api"
cmd /c "`"$Py\alembic.exe`" upgrade head > `"$Logs\migrate.log`" 2>&1"   # qua cmd: PS 5.1 coi stderr của lệnh native là lỗi
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Migration lỗi — xem $Logs\migrate.log" }
Pop-Location

# 4. API, worker, beat
Start-Svc "api" "$Py\uvicorn.exe" @("app.main:app", "--host", "127.0.0.1", "--port", "8000") "$Root\services\api"
Start-Svc "worker" "$Py\celery.exe" @("-A", "app.celery_app", "worker", "-Q", "generation,render,celery", "-l", "info",
    "--pool", "threads", "--concurrency", "2", "-n", "worker@$env:COMPUTERNAME") "$Root\services\worker"
Start-Svc "beat" "$Py\celery.exe" @("-A", "app.celery_app", "beat", "-l", "info", "--schedule", "$Data\run\celerybeat-schedule") "$Root\services\worker"

# 5. Web (bản build production; build nếu chưa có)
$web = "$Root\apps\web"
if (-not (Test-Path "$web\.next\BUILD_ID")) {
    Write-Host "  build web lần đầu (vài phút)..."
    Push-Location $web; cmd /c "npx next build > `"$Logs\web-build.log`" 2>&1"; $ok = $LASTEXITCODE; Pop-Location
    if ($ok -ne 0) { throw "Build web lỗi — xem $Logs\web-build.log" }
}
$env:API_PUBLIC_URL = "http://localhost:8000"
Start-Svc "web" "node.exe" @("node_modules\next\dist\bin\next", "start", "-p", $WebPort) $web

# 6. Chờ sẵn sàng
for ($i = 0; $i -lt 40; $i++) {
    try { $h = Invoke-RestMethod "http://localhost:8000/health/ready" -TimeoutSec 3; if ($h.status) { break } } catch { Start-Sleep 2 }
}
& "$PSScriptRoot\status.ps1"
Write-Host "`nMở: http://localhost:$WebPort"
