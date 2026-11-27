// Mart: tháng × khu vực đón × khu vực trả (A7, B5)
let
    Source = Parquet.Document(File.Contents(RepoFolder & "\data\bi\mart_routes_monthly.parquet")),
    WithMonthKey = Table.AddColumn(Source, "monthkey", each [year] * 100 + [month], Int64.Type),
    WithRoute = Table.AddColumn(WithMonthKey, "route",
        each [pickup_zone] & " → " & [dropoff_zone], type text)
in
    WithRoute
