param([switch]$MigrateOnly)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
  throw 'Python 3.13 .venv is missing. Run .\setup-local.ps1 first.'
}
$version = & $python -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ($LASTEXITCODE -ne 0 -or $version -ne '3.13') {
  throw 'Local development requires Python 3.13. Move the old .venv aside and run .\setup-local.ps1; do not force PyO3 compatibility.'
}

$environmentFile = Join-Path $projectRoot '.env'
if (-not (Test-Path -LiteralPath $environmentFile)) {
  throw 'Create the ignored local .env file from .env.example and set the local database connection first.'
}

Get-Content -LiteralPath $environmentFile | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith('#')) { return }
  $separator = $line.IndexOf('=')
  if ($separator -le 0) { return }
  $name = $line.Substring(0, $separator).Trim()
  $value = $line.Substring($separator + 1).Trim()
  if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
    $value = $value.Substring(1, $value.Length - 2)
  }
  Set-Item -Path "Env:$name" -Value $value
}

if ($env:APP_HOST -ne '127.0.0.1') {
  throw 'The local runner only binds to 127.0.0.1.'
}

# This runner (including migrations) is deliberately restricted to the Compose DB.
# Do not print the URL: a mistakenly supplied URL could contain a real secret.
$databaseCheck = @'
import os, sys
from urllib.parse import urlparse
try:
    url = urlparse(os.environ.get('DATABASE_URL', ''))
    valid = (url.scheme == 'postgresql+psycopg' and url.hostname == '127.0.0.1'
             and url.port == 5432 and url.username == 'gateway_local'
             and url.path == '/gateway_local' and not url.query and not url.fragment)
except ValueError:
    valid = False
sys.exit(0 if valid else 1)
'@
& $python -c $databaseCheck
if ($LASTEXITCODE -ne 0) {
  throw 'Local DATABASE_URL must target gateway_local as gateway_local on 127.0.0.1:5432, without URL options. See .env.example.'
}

# A stopped local database must fail promptly rather than hang libpq indefinitely.
$env:PGCONNECT_TIMEOUT = '5'
Push-Location (Join-Path $projectRoot 'backend')
try {
  if ($MigrateOnly) {
    & $python -m alembic upgrade head
  } else {
    & $python -m uvicorn 'app.main:app' '--host' '127.0.0.1' '--port' $env:APP_PORT
  }
  if ($LASTEXITCODE -ne 0) { throw "Local command failed (exit $LASTEXITCODE)." }
} finally {
  Pop-Location
}
