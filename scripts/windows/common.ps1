# Dùng chung cho các script Windows: đọc .env, đường dẫn dữ liệu, quản lý PID.
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$Root = (Resolve-Path "$PSScriptRoot\..\..").Path

function Import-DotEnv([string]$path) {
    foreach ($line in Get-Content $path -Encoding UTF8) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $k, $v = $line -split '=', 2
        $v = ($v -replace '\s+#.*$', '').Trim()
        [Environment]::SetEnvironmentVariable($k.Trim(), $v, "Process")
    }
}

Import-DotEnv "$Root\.env"
$Data = if ($env:ANNGAN_DATA_DIR) { $env:ANNGAN_DATA_DIR } else { "D:\AnhNganStudio" }
$Logs = "$Data\logs"; $Run = "$Data\run"
New-Item -ItemType Directory -Force $Logs, $Run, "$Data\tmp" | Out-Null
$env:TEMP = "$Data\tmp"; $env:TMP = "$Data\tmp"   # file tạm FFmpeg ra ổ dữ liệu
$env:PYTHONPATH = "$Root\services\api;$Root\services\worker"
$env:PYTHONUTF8 = "1"
$Py = "$Root\.venv\Scripts"
$PgBin = "$Data\pgsql\bin"
$env:Path = "$PgBin;$env:Path"   # pg_dump / pg_restore cho Backup (M15)

function Save-Pid([string]$name, $proc) { Set-Content "$Run\$name.pid" $proc.Id }

function Get-SvcProcess([string]$name) {
    $f = "$Run\$name.pid"
    if (-not (Test-Path $f)) { return $null }
    Get-Process -Id ([int](Get-Content $f)) -ErrorAction SilentlyContinue
}

function Start-Svc([string]$name, [string]$exe, [string[]]$argList, [string]$cwd) {
    if (Get-SvcProcess $name) { Write-Host "  $name đang chạy"; return }
    $p = Start-Process -FilePath $exe -ArgumentList $argList -WorkingDirectory $cwd -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput "$Logs\$name.log" -RedirectStandardError "$Logs\$name.err.log"
    Save-Pid $name $p
    Write-Host "  $name đã bật (PID $($p.Id))"
}
