import SwiftUI

@main
struct CalixApp: App {
    @State private var library = CalixLibrary()
    @Environment(\.scenePhase) private var phase

    var body: some Scene {
        WindowGroup {
            CalixRoot(library: library)
                .environment(\.locale, Locale(identifier: "ko_KR"))
                .onChange(of: phase) { _, newPhase in
                    if newPhase == .background { library.backgrounded() }
                    if newPhase == .active { library.finishFocusIfNeeded() }
                }
        }
    }
}

#if DEBUG
enum CalixScreenshot {
    static var page: String? {
        let args = ProcessInfo.processInfo.arguments
        guard let index = args.firstIndex(of: "-calix-screenshot"), args.indices.contains(index + 1) else { return nil }
        return args[index + 1]
    }

    static var tab: Int {
        switch page {
        case "deadlines": 1
        case "calendar": 2
        case "courses": 3
        case "more": 4
        default: 0
        }
    }

    static func seed(now: Date = .now) -> CalixData {
        func due(_ offset: Int) -> Date? {
            let calendar = Calendar.current
            return calendar.date(byAdding: .day, value: offset, to: now).flatMap {
                calendar.date(bySettingHour: 23, minute: 59, second: 59, of: $0)
            }
        }
        var result = CalixData()
        result.preferences.nickname = "민서"
        result.preferences.theme = .lavender
        result.canvasID = "fixture"
        result.lastSync = now
        result.events = [
            CalixEvent(title: "창업 아이디어 정리", course: "기업가정신", due: due(0), starred: true),
            CalixEvent(title: "읽기 자료 요약", course: "아카데믹 영어", due: due(-1)),
            CalixEvent(title: "이번 주 강의 영상", course: "세계문화의 이해", kind: .video, due: due(2)),
            CalixEvent(title: "에세이 개요 작성", course: "아카데믹 영어", due: due(4)),
            CalixEvent(title: "팀 발표 자료 제출", course: "기업가정신", due: due(10)),
            CalixEvent(title: "수업 안내 영상", course: "기업가정신", kind: .video, due: due(-4), done: true),
            CalixEvent(title: "발표 주제 투표", course: "아카데믹 영어", due: due(-4), done: true),
            CalixEvent(title: "강의 복습 영상", course: "세계문화의 이해", kind: .video)
        ]
        return result
    }
}
#endif
