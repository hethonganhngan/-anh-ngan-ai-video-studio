# Sao lưu CSDL (pg_dump) + nén media vào ANNGAN_DATA_DIR\backups; giữ 14 bản gần nhất.
# Hẹn giờ 2h sáng hằng ngày (chạy 1 lần, PowerShell quyền thường):
#   schtasks /Create /TN "AnhNganStudio-Backup" /SC DAILY /ST 02:00 /TR "powershell -ExecutionPolicy Bypass -File C:\ANHNGAN-PROJECTS\anh-ngan-ai-video-studio\scripts\windows\backup.ps1"
. "$PSScriptRoot\common.ps1"
Push-Location "$Root\services\api"
cmd /c "`"$Py\python.exe`" -c `"from app.modules.administration.backup import create_backup; print(create_backup(include_media=True))`" >> `"$Logs\backup.log`" 2>&1"
$ok = $LASTEXITCODE
Pop-Location
if ($ok -ne 0) { throw "Sao lưu lỗi — xem $Logs\backup.log" }
Get-ChildItem "$Data\backups" -File | Sort-Object LastWriteTime -Descending | Select-Object -Skip 28 | Remove-Item -Force
Write-Host "Đã sao lưu — xem $Logs\backup.log"
