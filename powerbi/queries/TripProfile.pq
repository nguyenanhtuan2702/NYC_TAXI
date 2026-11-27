// Mart: tháng × nhóm khách × mã giá × nhóm cự ly × thanh toán (A5, B1, B3)
let
    Source = Parquet.Document(File.Contents(RepoFolder & "\data\bi\mart_trip_profile.parquet")),
    WithMonthKey = Table.AddColumn(Source, "monthkey", each [year] * 100 + [month], Int64.Type)
in
    WithMonthKey
