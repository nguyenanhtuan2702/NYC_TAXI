// Mart: KPI theo tháng, tăng trưởng MoM/YoY (B2, B3, B4)
let
    Source = Parquet.Document(File.Contents(RepoFolder & "\data\bi\mart_monthly_kpi.parquet")),
    WithMonthKey = Table.AddColumn(Source, "monthkey", each [year] * 100 + [month], Int64.Type)
in
    WithMonthKey
