# Tải Yellow Taxi 2024-2025 (24 file Parquet) vào data/raw. Chạy: .\data\download_raw.ps1
$ProgressPreference = 'SilentlyContinue'
$dest = Join-Path $PSScriptRoot 'raw'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
foreach ($y in 2024,2025) { foreach ($m in 1..12) {
  $f = "yellow_tripdata_{0}-{1:00}.parquet" -f $y,$m
  $out = Join-Path $dest $f
  if (Test-Path $out) { Write-Host "SKIP $f"; continue }
  try {
    Invoke-WebRequest "https://d37ci6vzurychx.cloudfront.net/trip-data/$f" -OutFile $out
    Write-Host "OK   $f"
  } catch { Write-Host "LOI  $f : $($_.Exception.Message)"; Remove-Item $out -ErrorAction SilentlyContinue }
}}
