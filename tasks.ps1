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
                 'ingest-zones', 'ingest', 'e2e', 'e2e-direct', 'status', 'profile', 'dbt-deps', 'dbt-run', 'dbt-test',
                 'dbt-build', 'qa', 'export-bi', 'build-map', 'prune-branches')]
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
function Invoke-DuckDb([string]$Sql) {
    $Sql | docker compose exec -T mage python /home/src/sql/run_sql.py
}

# Chạy pipeline Mage không cần giao diện. PowerShell 5.1 làm mất dấu " khi truyền cho
# chương trình ngoài, nên JSON phải escape thành \".
function Invoke-MagePipeline([string]$Pipeline, [string]$VarsJson) {
    $cmd = @('compose', 'exec', '-T', 'mage', 'mage', 'run', '/home/src/mage', $Pipeline)
    if ($VarsJson) { $cmd += @('--runtime-vars', ($VarsJson -replace '"', '\"')) }
    # Mage in WARNING ra stderr. Khi output bị chuyển hướng (log, Task Scheduler), PowerShell 5.1
    # biến mỗi dòng stderr thành lỗi và $ErrorActionPreference = 'Stop' sẽ dừng script giữa chừng:
    # tạm dùng 'Continue', kết quả lấy từ $LASTEXITCODE.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & docker @cmd 2>&1 | ForEach-Object { "$_" } } finally { $ErrorActionPreference = $prev }
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
  ingest-zones                      Nạp Taxi Zone Lookup vào raw.taxi_zone_lookup
  ingest [file | ALL | JSON]        Nạp chuyến đi vào raw.yellow_tripdata, mặc định ALL
                                    vd: ingest yellow_tripdata_2024-01.parquet
                                        ingest '{"file_name":"ALL","year":2024}'
  e2e [JSON]                        Chạy pipeline nyc_taxi_e2e qua scheduler Mage (trigger manual_e2e:
                                    có retry, cảnh báo, timeout như lượt theo lịch), đợi đến khi xong
                                    Zone Lookup -> chuyến đi -> dbt build -> QA -> xuất Parquet Power BI
                                    vd: e2e '{"file_name": "yellow_tripdata_2025-03.parquet"}'
  e2e-direct [JSON]                 Chạy thẳng bằng `mage run` (không retry, không callback cảnh báo)
  status                            Lần chạy e2e thành công gần nhất (cảnh báo nếu quá 35 ngày),
                                    cảnh báo lỗi gần đây, trạng thái container
  profile <file.sql>                Chạy một truy vấn trong sql/profiling
  dbt-deps | dbt-run | dbt-test | dbt-build [selector]
                                    Chạy dbt trong container Mage (vd: dbt-build dim_vendor)
  qa [preflight|smoke|deep|all|full]
                                    Runner QA chỉ đọc trên DuckDB (mặc định smoke; full = all + quét lớn)
  export-bi                         Xuất OLAP mart + Dimension ra data/bi/*.parquet cho Power BI
  build-map                         Dựng lại powerbi/map_shapes (TopoJSON, tâm khu vực) từ shapefile
  prune-branches                    Xóa nhánh local mà nhánh remote đã bị xóa (sau khi merge PR)
'@
    }
    'up'           { docker compose up -d --build; docker compose ps }
    'down'         { docker compose down }
    'ps'           { docker compose ps }
    'logs'         { if ($Arg) { docker compose logs -f $Arg } else { docker compose logs -f } }
    'shell'        { docker compose exec mage bash }
    'sql' {
        if (-not $Arg) { throw 'Cần câu SQL, vd: .\tasks.ps1 sql "show all tables"' }
        Invoke-DuckDb $Arg
    }
    'download-raw' { powershell -ExecutionPolicy Bypass -File data\download_raw.ps1 }
    'ingest-zones' { Invoke-MagePipeline 'ingest_zone_lookup' $null }
    'ingest' {
        $vars = if (-not $Arg) { '{"file_name": "ALL"}' }
                elseif ($Arg.TrimStart().StartsWith('{')) { $Arg }
                else { '{"file_name": "' + $Arg + '"}' }
        Invoke-MagePipeline 'ingest_yellow_trips' $vars
    }
    'e2e' {
        # Tạo lượt chạy cho trigger API manual_e2e; scheduler trong server Mage thực thi giống lượt
        # theo lịch. PowerShell 5.1 làm mất dấu " khi truyền cho chương trình ngoài: escape thành \".
        $cmd = @('compose', 'exec', '-T', 'mage', 'python', '/home/src/mage/utils/trigger_run.py')
        if ($Arg) { $cmd += ($Arg -replace '"', '\"') }
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try { & docker @cmd 2>&1 | ForEach-Object { "$_" } } finally { $ErrorActionPreference = $prev }
        if ($LASTEXITCODE -ne 0) { throw "Pipeline nyc_taxi_e2e lỗi (mã $LASTEXITCODE)" }
    }
    'e2e-direct' {
        Invoke-MagePipeline 'nyc_taxi_e2e' $(if ($Arg) { $Arg } else { $null })
        if ($LASTEXITCODE -ne 0) { throw "Pipeline nyc_taxi_e2e lỗi (mã $LASTEXITCODE)" }
    }
    'status' {
        # Chạy trên máy host, không cần container. Lần xuất Parquet chỉ chạy khi mọi bước trước
        # thành công, nên thời điểm xuất = lần chạy pipeline thành công gần nhất.
        $manifest = 'data\bi\_manifest.json'
        if (Test-Path $manifest) {
            $exported = [datetimeoffset]::Parse((Get-Content $manifest -Raw -Encoding UTF8 | ConvertFrom-Json).exported_at_utc)
            $age = [int]([datetimeoffset]::UtcNow - $exported).TotalDays
            Write-Output ("Lần chạy thành công gần nhất (xuất Power BI): {0:yyyy-MM-dd HH:mm} UTC, cách đây {1} ngày" -f $exported.UtcDateTime, $age)
            if ($age -gt 35) { Write-Warning 'Quá 35 ngày: lượt chạy theo lịch hằng tháng đã bị lỡ hoặc lỗi. Chạy .\tasks.ps1 e2e' }
        } else {
            Write-Warning "Chưa có $manifest (pipeline chưa từng chạy hết)"
        }
        $alerts = 'data\warehouse\alerts\pipeline_alerts.jsonl'
        if (Test-Path $alerts) {
            Write-Output 'Cảnh báo lỗi gần nhất:'
            Get-Content $alerts -Encoding UTF8 -Tail 5 | ForEach-Object {
                $a = $_ | ConvertFrom-Json
                $msg = if ($a.error.Length -gt 150) { $a.error.Substring(0, 150) + '...' } else { $a.error }
                Write-Output ("  {0}  {1} / {2}: {3}" -f $a.at_utc.Substring(0, 16), $a.pipeline, $a.block, $msg)
            }
        } else {
            Write-Output 'Không có cảnh báo lỗi nào.'
        }
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try { docker compose ps --format '{{.Name}}: {{.Status}}' 2>&1 | ForEach-Object { "Container $_" } }
        finally { $ErrorActionPreference = $prev }
    }
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
        # Runner chạy trong container Mage (có thư viện duckdb), mở file DuckDB ở chế độ read_only.
        # full = suite all + các kiểm tra quét toàn bộ staging/Fact.
        $suite = if ($Arg) { $Arg } else { 'smoke' }
        $qaArgs = if ($suite -eq 'full') { @('--suite', 'all', '--include-large-scans') } else { @('--suite', $suite) }
        docker compose exec -T mage python /home/src/tests/run_quality_tests.py @qaArgs
    }
    'export-bi' { docker compose exec -T mage python /home/src/powerbi/scripts/export_bi.py }
    'build-map' { docker compose exec -T mage python /home/src/powerbi/scripts/build_map_shapes.py }
    'prune-branches' {
        git fetch --prune origin
        $current = git branch --show-current
        $gone = git branch -vv | Where-Object { $_ -match '\[origin/[^\]]+: gone\]' } |
            ForEach-Object { ($_.TrimStart('*', ' ') -split '\s+')[0] }
        if (-not $gone) { Write-Output 'Không có nhánh local nào cần dọn.'; return }
        foreach ($b in $gone) {
            if ($b -eq $current) { Write-Output "Bỏ qua $b (đang checkout; chuyển sang main trước)"; continue }
            # -d (không phải -D): git từ chối xóa nếu nhánh có commit chưa được merge
            git branch -d $b
        }
    }
}
