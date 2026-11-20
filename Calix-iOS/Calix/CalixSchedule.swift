import Foundation

struct Course: Identifiable {
    let id: String
    let name: String
    let symbol: String

    static let samples = [
        Course(id: "business", name: "기업가정신", symbol: "lightbulb"),
        Course(id: "writing", name: "아카데믹 영어", symbol: "text.book.closed"),
        Course(id: "culture", name: "세계문화의 이해", symbol: "globe.asia.australia")
    ]
}

struct ScheduleItem: Identifiable {
    enum Kind: String, CaseIterable, Identifiable {
        case assignment = "과제"
        case video = "영상"

        var id: Self { self }
        var symbol: String { self == .assignment ? "doc.text" : "play.rectangle" }
    }

    let id: String
    let course: Course
    let title: String
    let kind: Kind
    let dueAt: Date?

    static func samples(startingAt anchor: Date, calendar: Calendar = .current) -> [Self] {
        func due(_ days: Int, hour: Int) -> Date? {
            calendar.date(byAdding: .day, value: days, to: anchor).flatMap {
                calendar.date(bySettingHour: hour, minute: 59, second: 59, of: $0)
            }
        }

        let business = Course.samples[0]
        let writing = Course.samples[1]
        let culture = Course.samples[2]
        return [
            Self(id: "idea", course: business, title: "창업 아이디어 정리", kind: .assignment, dueAt: due(0, hour: 23)),
            Self(id: "reading", course: writing, title: "읽기 자료 요약", kind: .assignment, dueAt: due(-1, hour: 23)),
            Self(id: "week-video", course: culture, title: "이번 주 강의 영상", kind: .video, dueAt: due(2, hour: 23)),
            Self(id: "outline", course: writing, title: "에세이 개요 작성", kind: .assignment, dueAt: due(4, hour: 18)),
            Self(id: "presentation", course: business, title: "팀 발표 자료 제출", kind: .assignment, dueAt: due(10, hour: 23)),
            Self(id: "review", course: culture, title: "강의 복습 영상", kind: .video, dueAt: nil),
            Self(id: "introduction", course: business, title: "수업 소개 영상", kind: .video, dueAt: due(-3, hour: 23))
        ]
    }

    static func sorted(_ items: [Self]) -> [Self] {
        items.sorted {
            let lhs = $0.dueAt ?? .distantFuture
            let rhs = $1.dueAt ?? .distantFuture
            return lhs == rhs ? $0.title.localizedCompare($1.title) == .orderedAscending : lhs < rhs
        }
    }
}

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

struct ClassSession: Identifiable {
    let id: String
    let course: Course
    let weekday: Int
    let start: String
    let end: String
    let room: String

    static let samples = [
        Self(id: "business-mon", course: Course.samples[0], weekday: 2, start: "09:00", end: "10:00", room: "D301"),
        Self(id: "writing-tue", course: Course.samples[1], weekday: 3, start: "10:30", end: "12:00", room: "A204"),
        Self(id: "business-wed", course: Course.samples[0], weekday: 4, start: "09:00", end: "10:00", room: "D301"),
        Self(id: "culture-thu", course: Course.samples[2], weekday: 5, start: "13:00", end: "14:30", room: "B102"),
        Self(id: "writing-fri", course: Course.samples[1], weekday: 6, start: "10:30", end: "12:00", room: "A204")
    ]
}
