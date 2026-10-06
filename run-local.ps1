$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
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

$uvicorn = Join-Path $projectRoot '.venv\Scripts\uvicorn.exe'
if (-not (Test-Path -LiteralPath $uvicorn)) {
  throw 'Backend dependencies are missing. Install backend/requirements.txt in .venv first.'
}

Set-Location (Join-Path $projectRoot 'backend')
& $uvicorn 'app.main:app' '--host' '127.0.0.1' '--port' $env:APP_PORT
exit $LASTEXITCODE
