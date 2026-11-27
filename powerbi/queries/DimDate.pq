// Bảng ngày 2024-01-01 .. 2026-01-31; khóa datesk = YYYYMMDD
let
    Source = Parquet.Document(File.Contents(RepoFolder & "\data\bi\dimdate.parquet")),
    // Bỏ dòng Unknown (1900-01-01): bảng ngày đánh dấu "Mark as date table" phải liên tục, không trùng.
    // Mart không có khóa -1 (đã kiểm tra bằng runner QA FACT-KEY-01).
    NoUnknown = Table.SelectRows(Source, each [datesk] <> -1),
    WithMonthKey = Table.AddColumn(NoUnknown, "monthkey", each [year] * 100 + [month], Int64.Type),
    // Ngày đầu tháng (kiểu date): mức giữa của hierarchy Calendar (year > monthstart > fulldate),
    // cho phép trục X liên tục ở mức tháng, nhãn nằm ngang (không xoay chữ).
    WithMonthStart = Table.AddColumn(WithMonthKey, "monthstart", each Date.StartOfMonth([fulldate]), type date)
in
    WithMonthStart
