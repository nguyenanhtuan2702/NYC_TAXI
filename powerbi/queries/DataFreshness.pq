// Thời điểm dữ liệu được xuất cho Power BI (data/bi/_manifest.json, ghi ở bước cuối pipeline nyc_taxi_e2e).
// Một dòng; dùng cho card "Data as of" ở góc trên bên phải mỗi trang. Không tạo quan hệ.
let
    Source = Json.Document(File.Contents(RepoFolder & "\data\bi\_manifest.json"), 65001),
    ExportedUtc = DateTimeZone.FromText(Source[exported_at_utc]),
    Result = #table(
        type table [exported_at_utc = datetimezone, exported_at_local = datetime],
        {{ExportedUtc, DateTimeZone.RemoveZone(DateTimeZone.SwitchZone(ExportedUtc, 7))}}
    )
in
    Result
