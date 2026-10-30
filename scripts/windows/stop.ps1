# Tắt toàn bộ dịch vụ (theo PID đã lưu — không đụng tới tiến trình khác trên máy).
. "$PSScriptRoot\common.ps1"
foreach ($name in "web", "beat", "worker", "api", "vieneu", "redis") {
    $p = Get-SvcProcess $name
    if ($p) { taskkill /T /F /PID $p.Id *> $null; Write-Host "  $name đã tắt" }
    Remove-Item "$Run\$name.pid" -ErrorAction SilentlyContinue
}
& "$PgBin\pg_ctl.exe" -D "$Data\pgdata" -m fast stop *> $null
Write-Host "  postgres đã tắt"
