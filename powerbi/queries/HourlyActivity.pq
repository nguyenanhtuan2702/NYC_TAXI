// Mart: pickup/dropoff × ngày × giờ × quận (A4, 5b). Cộng doanh thu thì lọc MỘT vai trò
let
    Source = Parquet.Document(File.Contents(RepoFolder & "\data\bi\mart_hourly_activity.parquet"))
in
    Source
