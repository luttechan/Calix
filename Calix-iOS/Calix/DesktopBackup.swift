import Compression
import CryptoKit
import Foundation

enum DesktopBackup {
    enum Failure: Error { case encrypted, invalid }

    static func read(_ bytes: Data) throws -> CalixData {
        if bytes.starts(with: Data("Calix password backup v1\0".utf8)) { throw Failure.encrypted }
        let rootBytes = try decodeEntry(bytes)
        let source = try JSONDecoder().decode(Archive.self, from: rootBytes)
        guard source.format == "Calix personal backup", (1...7).contains(source.version) else { throw Failure.invalid }

        // Keep imported IDs stable so re-importing updates the same entries.
        let courses = Dictionary(source.schedule.courses.map { ($0.id, $0.name) }, uniquingKeysWith: { first, _ in first })
        let checklist = source.checklist
        let sections = Dictionary((checklist?.sections ?? []).map { ($0.id, $0.name) }, uniquingKeysWith: { first, _ in first })
        let statuses = Dictionary((checklist?.statuses ?? []).map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        var output = CalixData()
        output.events = source.schedule.events.filter { !$0.title.trimmed.isEmpty && $0.key.hasPrefix("manual:") }.map { event in
            CalixEvent(id: "desktop:\(event.key)", title: event.title, course: courses[event.course_id] ?? "", kind: .personal,
                       due: event.due_at.flatMap(calixDate), note: event.note ?? "", done: event.completed == 1,
                       starred: event.starred == 1, seriesID: event.series_id.flatMap { $0.isEmpty ? nil : "desktop:\($0)" })
        }
        output.lessons = source.schedule.timetable.enumerated().compactMap { index, lesson in
            let title = lesson.title?.trimmed ?? ""
            let resolved = title.isEmpty ? (courses[lesson.course_id] ?? "") : title
            guard !resolved.isEmpty, (0...6).contains(lesson.day) else { return nil }
            let online = lesson.is_online == 1
            let start = minutes(lesson.start_time) ?? 540
            let end = minutes(lesson.end_time) ?? 600
            guard online || start < end else { return nil }
            let identity = lesson.id.map(String.init) ?? "\(lesson.course_id):\(lesson.day):\(start):\(index)"
            return CalixLesson(id: uuid("lesson:\(identity)"), title: resolved,
                               term: lesson.semester?.isEmpty == false ? (lesson.semester ?? "기본 학기") : "기본 학기",
                               weekday: (lesson.day + 1) % 7 + 1, start: start, end: end,
                               room: lesson.room ?? "", lecturer: lesson.professor ?? "", online: online)
        }
        output.tasks = (checklist?.tasks ?? []).filter { $0.trashed != 1 && !$0.title.trimmed.isEmpty }.map { task in
            let status = statuses[task.status_id ?? -1]
            return CalixTask(id: uuid("task:\(task.id)"), title: task.title, section: sections[task.section_id] ?? "기본",
                             done: status?.kind == "done", status: status?.name,
                             due: task.due_at.flatMap(calixDate), note: task.note, role: task.role, instructor: task.professor)
        }
        output.grades = (source.grades ?? []).filter { (0...30).contains($0.credits) && !$0.title.trimmed.isEmpty }.map {
            CalixGrade(id: uuid("grade:\($0.semester):\($0.id)"), title: $0.title, term: $0.semester, credits: $0.credits,
                       mark: $0.grade, category: $0.category, excluded: $0.excluded == 1)
        }
        output.gradeScales = Dictionary((source.grade_scales ?? []).compactMap { row -> (String, Double)? in
            guard let scale = Double(row.scale), [4.0, 4.3, 4.5].contains(scale) else { return nil }
            return (row.semester, scale)
        }, uniquingKeysWith: { first, _ in first })
        output.journals = source.journals.compactMap {
            guard let date = calixDate($0.date) else { return nil }
            return CalixJournal(id: uuid("diary:\($0.id)"), date: date, title: $0.title, body: $0.body)
        }
        output.focusHistory = (source.focus_sessions ?? []).compactMap {
            guard let date = calixDate($0.day), (1...86400).contains($0.seconds) else { return nil }
            return CalixFocusRecord(id: uuid("focus:\($0.id)"), started: date, seconds: $0.seconds)
        }
        for holiday in source.holiday_overrides ?? [] where holiday.enabled == 1 {
            if let value = calixDate(holiday.day) { output.holidays[CalixData.dayKey(value)] = holiday.name }
        }
        return output
    }

    private static func decodeEntry(_ bytes: Data) throws -> Data {
        func integer(_ offset: Int, _ size: Int) -> Int {
            (0..<size).reduce(0) { value, index in value | (Int(bytes[offset + index]) << (8 * index)) }
        }
        // The desktop writer emits a single local record with a known entry name and declared sizes.
        guard bytes.count >= 40, integer(0, 4) == 0x04034b50, integer(6, 2) & 9 == 0 else { throw Failure.invalid }
        let method = integer(8, 2)
        let compressed = integer(18, 4)
        let expanded = integer(22, 4)
        let nameLength = integer(26, 2)
        let begin = 30 + nameLength + integer(28, 2)
        guard nameLength == 10, bytes[30..<40].elementsEqual("calix.json".utf8),
              compressed > 0, expanded > 0, expanded <= 32 * 1024 * 1024,
              begin <= bytes.count, compressed <= bytes.count - begin else { throw Failure.invalid }
        let compressedBytes = Data(bytes[begin..<(begin + compressed)])
        if method == 0, expanded == compressed { return compressedBytes }
        guard method == 8 else { throw Failure.invalid }
        var output = Data(count: expanded + 1)
        let count = output.withUnsafeMutableBytes { destination in
            compressedBytes.withUnsafeBytes { source in
                guard let dst = destination.bindMemory(to: UInt8.self).baseAddress,
                      let src = source.bindMemory(to: UInt8.self).baseAddress else { return 0 }
                return compression_decode_buffer(dst, expanded + 1, src, compressed, nil, COMPRESSION_ZLIB)
            }
        }
        guard count == expanded else { throw Failure.invalid }
        output.removeLast()
        return output
    }

    private static func minutes(_ text: String?) -> Int? {
        guard let text else { return nil }
        let parts = text.split(separator: ":").compactMap { Int($0) }
        guard parts.count == 2, (0..<24).contains(parts[0]), (0..<60).contains(parts[1]) else { return nil }
        return parts[0] * 60 + parts[1]
    }

    private static func calixDate(_ text: String) -> Date? {
        if text.count == 10 {
            let date = DateFormatter()
            date.locale = Locale(identifier: "en_US_POSIX")
            date.dateFormat = "yyyy-MM-dd"
            return date.date(from: text)
        }
        let timestamp = ISO8601DateFormatter()
        timestamp.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = timestamp.date(from: text) { return date }
        timestamp.formatOptions = [.withInternetDateTime]
        return timestamp.date(from: text)
    }

    private static func uuid(_ value: String) -> UUID {
        let bytes = Array(SHA256.hash(data: Data(value.utf8)))
        return UUID(uuid: (bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7],
                           bytes[8], bytes[9], bytes[10], bytes[11], bytes[12], bytes[13], bytes[14], bytes[15]))
    }

    private struct Archive: Decodable {
        let format: String
        let version: Int
        let schedule: Schedule
        let checklist: Checklist?
        let grades: [Grade]?
        let grade_scales: [GradeScale]?
        let focus_sessions: [Focus]?
        let journals: [Diary]
        let holiday_overrides: [Holiday]?
    }

    private struct Schedule: Decodable {
        let courses: [Named]
        let events: [Event]
        let timetable: [Lesson]
    }

    private struct Checklist: Decodable {
        let sections: [Named]
        let statuses: [Status]
        let tasks: [ChecklistRow]
    }

    private struct Named: Decodable { let id: Int; let name: String }
    private struct Status: Decodable { let id: Int; let name: String; let kind: String }
    private struct Event: Decodable {
        let key: String; let course_id: Int; let title: String; let due_at: String?; let note: String?
        let completed: Int?; let starred: Int?; let series_id: String?
    }
    private struct Lesson: Decodable {
        let id: Int?; let course_id: Int; let title: String?; let semester: String?; let day: Int
        let start_time: String?; let end_time: String?; let room: String?; let professor: String?; let is_online: Int?
    }
    private struct ChecklistRow: Decodable {
        let id: String; let section_id: Int; let title: String; let due_at: String?; let note: String?
        let role: String?; let professor: String?; let status_id: Int?; let trashed: Int?
    }
    private struct Grade: Decodable {
        let id: String; let title: String; let semester: String; let credits: Double; let grade: String; let category: String?; let excluded: Int?
    }
    private struct GradeScale: Decodable { let semester: String; let scale: String }
    private struct Focus: Decodable { let id: String; let day: String; let seconds: Int }
    private struct Diary: Decodable { let id: String; let date: String; let title: String; let body: String }
    private struct Holiday: Decodable { let day: String; let name: String; let enabled: Int }
}
