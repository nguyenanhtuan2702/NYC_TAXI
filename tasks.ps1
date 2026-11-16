<#
.SYNOPSIS
  Lệnh thường dùng của dự án. Chạy từ thư mục gốc repo.

.EXAMPLE
  .\tasks.ps1 up
  .\tasks.ps1 dbt-build
  .\tasks.ps1 profile 03_profile_by_vendor.sql
  .\tasks.ps1 qa smoke
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('help', 'up', 'down', 'ps', 'logs', 'shell', 'sql', 'download-raw',
                 'profile', 'dbt-deps', 'dbt-run', 'dbt-test', 'dbt-build', 'qa')]
    [string]$Task = 'help',

    [Parameter(Position = 1)]
    [string]$Arg
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
# PowerShell 5.1 mặc định pipe sang chương trình ngoài bằng ASCII, làm hỏng chữ có dấu
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# Chạy SQL (đọc từ stdin) trên file DuckDB trong container Mage, chế độ chỉ đọc.
# DuckDB chỉ cho một tiến trình ghi: lệnh sẽ lỗi nếu dbt/Mage đang ghi vào file.
$DuckDbQuery = "import duckdb, os, sys; con = duckdb.connect(os.environ['DUCKDB_PATH'], read_only=True); con.sql(sys.stdin.read()).show(max_rows=200)"
function Invoke-DuckDb([string]$Sql) {
    $Sql | docker compose exec -T mage python -c $DuckDbQuery
}

# dbt chạy trong container Mage
function Invoke-Dbt([string[]]$DbtArgs) {
    docker compose exec -T mage dbt @DbtArgs --project-dir /home/src/dbt --profiles-dir /home/src/dbt
}

switch ($Task) {
    'help' {
        Write-Output @'
Tasks:
  up | down | ps | logs [service]   Quản lý Docker Compose
  shell                             Mở bash trong container Mage
  sql "<câu SQL>"                   Truy vấn file DuckDB (chỉ đọc)
  download-raw                      Tải trước Parquet vào data/raw (tùy chọn)
  profile <file.sql>                Chạy một truy vấn trong sql/profiling
  dbt-deps | dbt-run | dbt-test | dbt-build [selector]
                                    Chạy dbt trong container Mage (vd: dbt-build dim_vendor)
  qa [smoke|deep|all]               Chạy runner QA chỉ đọc (mặc định smoke)
'@
    }
    'up'           { docker compose up -d --build; docker compose ps }
    'down'         { docker compose down }
    'ps'           { docker compose ps }
    'logs'         { if ($Arg) { docker compose logs -f $Arg } else { docker compose logs -f } }
    'shell'        { docker compose exec mage bash }
    'sql' {
        if (-not $Arg) { throw 'Cần câu SQL, vd: .	asks.ps1 sql "show all tables"' }
        Invoke-DuckDb $Arg
    }
    'download-raw' { powershell -ExecutionPolicy Bypass -File data\download_raw.ps1 }
    'profile' {
        if (-not $Arg) { throw 'Cần tên file, vd: .\tasks.ps1 profile 03_profile_by_vendor.sql' }
        $file = Join-Path 'sql\profiling' $Arg
        if (-not (Test-Path $file)) { throw "Không tìm thấy $file" }
        Invoke-DuckDb ((Get-Content $file -Raw -Encoding UTF8))
    }
    'dbt-deps'  { Invoke-Dbt @('deps') }
    'dbt-run'   { if ($Arg) { Invoke-Dbt @('run', '--select', $Arg) } else { Invoke-Dbt @('run') } }
    'dbt-test'  { if ($Arg) { Invoke-Dbt @('test', '--select', $Arg) } else { Invoke-Dbt @('test') } }
    'dbt-build' { if ($Arg) { Invoke-Dbt @('build', '--select', $Arg) } else { Invoke-Dbt @('build') } }
    'qa' {
        $suite = if ($Arg) { $Arg } else { 'smoke' }
        python tests\run_quality_tests.py --suite $suite
    }
}
