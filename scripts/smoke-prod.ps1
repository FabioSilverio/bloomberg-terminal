param(
    [switch]$KeepUp
)

$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw '[smoke] docker is required.'
}

if (-not (Test-Path '.env') -and (Test-Path '.env.example')) {
    Copy-Item '.env.example' '.env'
    Write-Host '[smoke] .env created from .env.example'
}

function Wait-Http {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 180
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 8
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Host "[smoke] ok: $Name ($Url)"
                return
            }
        }
        catch {
            Start-Sleep -Seconds 3
        }
    } while ((Get-Date) -lt $deadline)

    throw "[smoke] timeout waiting for $Name ($Url)"
}

try {
    Write-Host '[smoke] building and starting stack'
    docker compose up --build -d | Out-Host

    Wait-Http -Name 'backend readiness' -Url 'http://localhost/api/v1/health/ready' -TimeoutSeconds 240
    Wait-Http -Name 'frontend' -Url 'http://localhost' -TimeoutSeconds 180
    Wait-Http -Name 'market overview API' -Url 'http://localhost/api/v1/market/overview' -TimeoutSeconds 180

    Write-Host '[smoke] ✅ production-like local smoke check passed'
}
finally {
    if (-not $KeepUp) {
        Write-Host '[smoke] stopping stack'
        docker compose down --remove-orphans | Out-Host
    }
    else {
        Write-Host '[smoke] stack kept running (-KeepUp)'
    }
}
