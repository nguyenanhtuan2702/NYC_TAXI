// Bảng tháng dựng từ DimDate: một slicer Năm/Tháng lọc được mọi mart
// (DimMonth -> DimDate -> TripsDaily/HourlyActivity; DimMonth -> RoutesMonthly/TripProfile/MonthlyKPI).
let
    Source = DimDate,
    Months = Table.Distinct(Table.SelectColumns(Source, {"monthkey", "year", "quarter", "month", "monthname"})),
    WithStart = Table.AddColumn(Months, "monthstart", each #date([year], [month], 1), type date),
    WithLabel = Table.AddColumn(WithStart, "yearmonth",
        each Text.From([year]) & "-" & Text.PadStart(Text.From([month]), 2, "0"), type text),
    // Tên tháng 3 chữ cho trục biểu đồ (12 nhãn nằm ngang, không xoay chữ). Sort by column: month.
    WithShort = Table.AddColumn(WithLabel, "monthshort", each Text.Start([monthname], 3), type text)
in
    WithShort
