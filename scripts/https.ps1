# Sirve a Muyu por HTTPS en la red local: los navegadores solo dan el micrófono
# en HTTPS (o en localhost), así que hace falta para hablarle desde el celular.
#
# Uso (desde la raíz del proyecto):   .\scripts\https.ps1
# Requisito: mkcert  ->  winget install FiloSottile.mkcert   (y una vez: mkcert -install)

param([int]$Puerto = 8443)

$raiz = Split-Path $PSScriptRoot -Parent
$certs = Join-Path $raiz "certs"
$python = Join-Path $raiz ".venv\Scripts\python.exe"

if (-not (Get-Command mkcert -ErrorAction SilentlyContinue)) {
    Write-Host "Falta mkcert. Instálalo con:  winget install FiloSottile.mkcert" -ForegroundColor Yellow
    Write-Host "Luego, una sola vez:          mkcert -install" -ForegroundColor Yellow
    exit 1
}

$ips = @(Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
    Select-Object -ExpandProperty IPAddress)

New-Item -ItemType Directory -Force $certs | Out-Null
$cert = Join-Path $certs "cert.pem"
$clave = Join-Path $certs "key.pem"
$nombres = Join-Path $certs "nombres.txt"
$deseados = (@("localhost", "127.0.0.1") + $ips) -join " "
# Se regeneran si cambió la IP de la PC.
if (-not (Test-Path $cert) -or -not (Test-Path $nombres) -or (Get-Content $nombres -Raw).Trim() -ne $deseados) {
    & mkcert -key-file $clave -cert-file $cert localhost 127.0.0.1 @ips
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Set-Content -Path $nombres -Value $deseados -Encoding utf8
}

Write-Host ""
Write-Host "Muyu por HTTPS:" -ForegroundColor Green
Write-Host "  En esta PC:   https://localhost:$Puerto"
foreach ($ip in $ips) { Write-Host "  En el celular (misma wifi):  https://${ip}:$Puerto" }
Write-Host "  Si el celular muestra un aviso de seguridad, acéptalo (o instala en él el certificado raíz de mkcert)."
Write-Host ""

Set-Location $raiz
& $python -m uvicorn server.main:app --host 0.0.0.0 --port $Puerto --ssl-keyfile $clave --ssl-certfile $cert
