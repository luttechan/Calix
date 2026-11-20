import Foundation

enum DeadlineGroup: String, CaseIterable, Identifiable {
    case overdue = "기한 경과"
    case today = "오늘"
    case week = "7일 이내"
    case later = "이후"
    case undated = "기한 없음"

    var id: Self { self }

    static func classify(_ dueAt: Date?, now: Date, calendar: Calendar = .current) -> Self {
        guard let dueAt else { return .undated }
        if dueAt < now { return .overdue }
        if calendar.isDate(dueAt, inSameDayAs: now) { return .today }
        guard let limit = calendar.date(byAdding: .day, value: 7, to: now) else { return .later }
        return dueAt <= limit ? .week : .later
    }
}
