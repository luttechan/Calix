import CryptoKit
import Foundation
import LocalAuthentication
import Observation
import Security
import UserNotifications

struct CalixEvent: Codable, Identifiable, Equatable {
    var id = UUID().uuidString
    var title = ""
    var course = ""
    var kind: EventKind = .assignment
    var due: Date? = nil
    var note = ""
    var done = false
    var starred = false
    var remote = false
    var manualCompletion: Bool? = nil
    var url: URL? = nil
    var feedback: String? = nil
    var seriesID: String? = nil
}

enum EventKind: String, Codable, CaseIterable, Identifiable {
    case assignment = "과제"
    case video = "영상"
    case personal = "개인 일정"
    var id: Self { self }
    var symbol: String {
        switch self {
        case .assignment: "doc.text"
        case .video: "play.rectangle"
        case .personal: "calendar"
        }
    }
}

struct CalixTask: Codable, Identifiable {
    var id = UUID()
    var title = ""
    var section = "기본"
    var done = false
    var status: String?
    var due: Date?
    var note: String?
    var role: String?
    var instructor: String?
    var sourceID: String?
}

struct CalixLesson: Codable, Identifiable {
    var id = UUID()
    var title = ""
    var term = "기본 학기"
    var weekday = 2
    var start = 540
    var end = 600
    var room = ""
    var lecturer = ""
    var online = false
}

struct CalixGrade: Codable, Identifiable {
    var id = UUID()
    var title = ""
    var term = "기본 학기"
    var credits = 3.0
    var mark = "A"
    var category: String?
    var excluded: Bool?
}

struct CalixJournal: Codable, Identifiable {
    var id = UUID()
    var date = Date()
    var title = ""
    var body = ""
    var secret = false
}

struct CalixFocus: Codable, Identifiable {
    var id = UUID()
    var started = Date()
    var seconds: Int? = 1500
    var endsAt: Date? { seconds.map { started.addingTimeInterval(Double($0)) } }
}

struct CalixFocusRecord: Codable, Identifiable {
    var id: UUID
    var started: Date
    var seconds: Int
}

struct CalixAttendance: Codable, Identifiable {
    var id: String
    var course: String
    var title: String
    var status: String
    var date: Date?
}

enum CalixTheme: String, Codable, Identifiable, CaseIterable {
    case sky = "스카이", pink = "핑크", mint = "민트", purple = "퍼플", dark = "다크"
    case peach = "피치", amber = "앰버", olive = "올리브", lavender = "라벤더"
    var id: Self { self }
    var hue: Double {
        switch self {
        case .sky: 0.59
        case .pink: 0.91
        case .mint: 0.46
        case .purple, .dark: 0.74
        case .peach: 0.04
        case .amber: 0.11
        case .olive: 0.24
        case .lavender: 0.69
        }
    }
}

struct CalixPreferences: Codable {
    var nickname = ""
    var homeMessage = "오늘의 학습 일정"
    var theme = CalixTheme.lavender
    var lockOnBackground = false
    var lockTimetable = false
    var notify = false
    var notifyMinutes = 60
    var notifySound = true
    var focusMessage = "집중할 시간입니다."
    var focusDoneMessage = "집중 시간이 끝났습니다."
    var gradeScale = 4.5
    var mainTerm = "기본 학기"
    var showAttendance = true
}

struct CalixData: Codable {
    var version = 1
    var preferences = CalixPreferences()
    var events: [CalixEvent] = []
    var tasks: [CalixTask] = []
    var lessons: [CalixLesson] = []
    var grades: [CalixGrade] = []
    var gradeScales: [String: Double]?
    var journals: [CalixJournal] = []
    var focusHistory: [CalixFocusRecord] = []
    var focus: CalixFocus?
    var attendance: [CalixAttendance] = []
    var holidays: [String: String] = [:]
    var offDays: [String: String] = [:]
    var avatar: Data?
    var canvasID: String?
    var lastSync: Date?

    static func dayKey(_ date: Date) -> String {
        let values = Calendar.current.dateComponents([.year, .month, .day], from: date)
        return String(format: "%04d-%02d-%02d", values.year ?? 0, values.month ?? 0, values.day ?? 0)
    }
}

@MainActor
@Observable
final class CalixLibrary {
    private(set) var data = CalixData()
    private(set) var unavailable = false
    var locked = false
    var issue: String?
    private let vault = CalixDisk()
    private var notificationUpdate: Task<Void, Never>?

    init() { reload() }

    func reload() {
        do {
            data = try vault.load()
            locked = data.preferences.lockOnBackground
            unavailable = false
        } catch {
            unavailable = true
            issue = "저장한 데이터를 열지 못했습니다. 기기 잠금을 해제하고 다시 시도하세요."
        }
    }

    @discardableResult
    func update(_ change: (inout CalixData) -> Void) -> Bool {
        guard !unavailable, !locked else { return false }
        var updated = data
        change(&updated)
        do {
            try vault.save(updated)
            let schedulesChanged = updated.events != data.events || updated.preferences.notify != data.preferences.notify ||
                updated.preferences.notifyMinutes != data.preferences.notifyMinutes || updated.preferences.notifySound != data.preferences.notifySound
            if let focus = data.focus, updated.focus?.id != focus.id {
                UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: ["calix.focus.\(focus.id)"])
            }
            data = updated
            if schedulesChanged { refreshReminders() }
            return true
        } catch {
            issue = "변경 내용을 저장하지 못했습니다. 기기의 저장 공간과 잠금 상태를 확인하세요."
            return false
        }
    }

    func backgrounded() {
        if data.preferences.lockOnBackground { locked = true }
    }

    func authenticate(_ reason: String) async -> Bool {
        let context = LAContext()
        guard context.canEvaluatePolicy(.deviceOwnerAuthentication, error: nil) else {
            issue = "iPhone 설정에서 기기 암호를 먼저 설정하세요."
            return false
        }
        do { return try await context.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: reason) }
        catch { return false }
    }

    func startFocus(seconds: Int?) {
        let focus = CalixFocus(seconds: seconds)
        guard update({ $0.focus = focus }), let seconds else { return }
        let title = data.preferences.focusDoneMessage
        let sound = data.preferences.notifySound
        Task {
            let center = UNUserNotificationCenter.current()
            guard (try? await center.requestAuthorization(options: [.alert, .sound])) == true,
                  data.focus?.id == focus.id, let end = focus.endsAt, end > Date() else { return }
            let content = UNMutableNotificationContent()
            content.title = title
            if sound { content.sound = .default }
            let trigger = UNTimeIntervalNotificationTrigger(timeInterval: max(1, end.timeIntervalSinceNow), repeats: false)
            try? await center.add(UNNotificationRequest(identifier: "calix.focus.\(focus.id)", content: content, trigger: trigger))
            if data.focus?.id != focus.id {
                center.removePendingNotificationRequests(withIdentifiers: ["calix.focus.\(focus.id)"])
            }
        }
    }

    func finishFocusIfNeeded(_ now: Date = .now) {
        guard let end = data.focus?.endsAt, end <= now else { return }
        stopFocus(at: end)
    }

    func stopFocus(at date: Date = .now) {
        guard let focus = data.focus else { return }
        let seconds = max(0, Int(date.timeIntervalSince(focus.started)))
        update { draft in
            if seconds > 0 {
                draft.focusHistory.append(CalixFocusRecord(id: focus.id, started: focus.started, seconds: seconds))
            }
            draft.focus = nil
        }
    }

    func setReminders(_ enabled: Bool) async {
        if enabled {
            guard (try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound])) == true else {
                issue = "iPhone 설정에서 Calix 알림을 허용하세요."
                return
            }
        }
        update { $0.preferences.notify = enabled }
    }

    func refreshReminders() {
        notificationUpdate?.cancel()
        notificationUpdate = Task {
            let center = UNUserNotificationCenter.current()
            let prefix = "calix.deadline."
            let pending = await center.pendingNotificationRequests()
            guard !Task.isCancelled else { return }
            center.removePendingNotificationRequests(withIdentifiers: pending.map(\.identifier).filter { $0.hasPrefix(prefix) })
            guard data.preferences.notify else { return }
            let interval = Double(data.preferences.notifyMinutes) * 60
            let upcoming = data.events.compactMap { event -> (CalixEvent, Date)? in
                guard !event.done, let due = event.due else { return nil }
                let fire = due.addingTimeInterval(-interval)
                guard fire.timeIntervalSinceNow >= 1 else { return nil }
                return (event, fire)
            }.sorted { $0.1 < $1.1 }.prefix(50)
            for (event, fire) in upcoming {
                guard !Task.isCancelled else { return }
                let content = UNMutableNotificationContent()
                content.title = "마감 알림"
                content.body = event.title
                if data.preferences.notifySound { content.sound = .default }
                let trigger = UNTimeIntervalNotificationTrigger(timeInterval: max(1, fire.timeIntervalSinceNow), repeats: false)
                let id = prefix + event.id
                try? await center.add(UNNotificationRequest(identifier: id, content: content, trigger: trigger))
            }
        }
    }
}

private struct CalixDisk {
    private let service = "io.github.luttechan.calix.ios.storage"
    private let account = "library-v1"

    private func file() throws -> URL {
        let folder = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        return folder.appendingPathComponent("calix-library.v1")
    }

    func load() throws -> CalixData {
        let path = try file()
        let bytes: Data
        do { bytes = try Data(contentsOf: path) }
        catch let error as CocoaError where error.code == .fileReadNoSuchFile { return CalixData() }
        let box = try AES.GCM.SealedBox(combined: bytes)
        return try JSONDecoder().decode(CalixData.self, from: AES.GCM.open(box, using: key(create: false)))
    }

    func save(_ data: CalixData) throws {
        let bytes = try JSONEncoder().encode(data)
        let box = try AES.GCM.seal(bytes, using: key(create: true))
        guard let combined = box.combined else { throw CocoaError(.fileWriteUnknown) }
        try combined.write(to: file(), options: [.atomic, .completeFileProtection])
    }

    private func key(create: Bool) throws -> SymmetricKey {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        var result: CFTypeRef?
        var request = query
        request[kSecMatchLimit as String] = kSecMatchLimitOne
        request[kSecReturnData as String] = true
        let status = SecItemCopyMatching(request as CFDictionary, &result)
        if status == errSecSuccess, let bytes = result as? Data, bytes.count == 32 {
            return SymmetricKey(data: bytes)
        }
        guard status == errSecItemNotFound, create else { throw CocoaError(.fileReadNoPermission) }
        let key = SymmetricKey(size: .bits256)
        request = query
        request[kSecValueData as String] = key.withUnsafeBytes { Data($0) }
        request[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        guard SecItemAdd(request as CFDictionary, nil) == errSecSuccess else { throw CocoaError(.fileWriteNoPermission) }
        return key
    }
}
