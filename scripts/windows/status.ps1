# Trạng thái dịch vụ + /health/ready.
. "$PSScriptRoot\common.ps1"
foreach ($name in "redis", "api", "worker", "beat", "web") {
    $p = Get-SvcProcess $name
    Write-Host ("  {0,-7} {1}" -f $name, $(if ($p) { "chạy (PID $($p.Id))" } else { "TẮT" }))
}
try {
    $h = Invoke-RestMethod "http://localhost:8000/health/ready" -TimeoutSec 5
    Write-Host "  health: $($h.status)"
    $h.checks.PSObject.Properties | ForEach-Object { Write-Host ("    {0,-9} {1}" -f $_.Name, $(if ($_.Value.ok) { "OK" } else { "LỖI $($_.Value.error)" })) }
} catch { Write-Host "  health: API chưa phản hồi" }
