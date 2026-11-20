import SwiftUI
import WebKit

@MainActor
final class CanvasBrowser: NSObject, WKNavigationDelegate, WKUIDelegate {
    static let startURL = URL(string: "https://canvas.bufs.ac.kr/login")!
    let view: WKWebView

    override init() {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        view = WKWebView(frame: .zero, configuration: config)
        super.init()
        view.navigationDelegate = self
        view.uiDelegate = self
        view.load(URLRequest(url: Self.startURL))
    }

    nonisolated static func isCampus(_ url: URL) -> Bool {
        guard url.scheme == "https", url.port == nil || url.port == 443,
              url.user == nil, url.password == nil, let host = url.host else { return false }
        return host == "bufs.ac.kr" || host.hasSuffix(".bufs.ac.kr")
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction) async -> WKNavigationActionPolicy {
        guard let url = action.request.url else { return .cancel }
        if action.targetFrame?.isMainFrame == false && url.absoluteString == "about:blank" { return .allow }
        return Self.isCampus(url) ? .allow : .cancel
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url, Self.isCampus(url) { webView.load(navigationAction.request) }
        return nil
    }

    static func clearSession() async {
        let store = WKWebsiteDataStore.default()
        await store.removeData(ofTypes: WKWebsiteDataStore.allWebsiteDataTypes(), modifiedSince: .distantPast)
    }
}

private struct CampusWebView: UIViewRepresentable {
    let browser: CanvasBrowser
    func makeUIView(context: Context) -> WKWebView { browser.view }
    func updateUIView(_ uiView: WKWebView, context: Context) {}
}

struct CalixCanvas: View {
    let library: CalixLibrary
    @State private var browser: CanvasBrowser?
    @State private var syncTask: Task<Void, Never>?
    @State private var message = "학교 계정으로 로그인한 뒤 동기화를 누르세요."

    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 8) {
                Text(message).font(.subheadline)
                if let time = library.data.lastSync {
                    Text("최근 동기화 \(time.formatted(.dateTime.month().day().hour().minute()))").font(.caption).foregroundStyle(.secondary)
                }
                if syncTask != nil {
                    HStack {
                        ProgressView()
                        Text("학교 일정 확인 중")
                        Spacer()
                        Button("중단") { cancel() }
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding()
            if let browser { CampusWebView(browser: browser) } else { ProgressView().frame(maxHeight: .infinity) }
        }
        .navigationTitle("학교 동기화")
        .navigationBarTitleDisplayMode(.inline)
        .task { if browser == nil { browser = CanvasBrowser() } }
        .onDisappear { cancel() }
        .toolbar {
            Button("동기화") { sync() }.disabled(browser == nil || syncTask != nil)
        }
    }

    private func cancel() {
        guard let syncTask else { return }
        syncTask.cancel()
        browser?.view.reload()
        message = "동기화를 중단하는 중입니다."
    }

    private func sync() {
        guard let browser, browser.view.url?.host == "canvas.bufs.ac.kr",
              browser.view.url?.scheme == "https", !browser.view.isLoading else {
            message = "학교 로그인 화면이 열릴 때까지 기다려 주세요."
            return
        }
        syncTask = Task {
            defer { syncTask = nil }
            do {
                guard let path = Bundle.main.url(forResource: "CanvasSync", withExtension: "js") else { throw CocoaError(.fileReadNoSuchFile) }
                let script = try String(contentsOf: path, encoding: .utf8)
                let arguments: [String: Any] = ["expectedOwner": library.data.canvasID ?? "", "includeAttendance": library.data.preferences.showAttendance]
                let result = try await browser.view.callAsyncJavaScript(script, arguments: arguments, in: nil, contentWorld: .page)
                try Task.checkCancellation()
                guard let value = result as? String, value.utf8.count < 20_000_000 else { throw CocoaError(.fileReadCorruptFile) }
                let decoder = JSONDecoder()
                decoder.dateDecodingStrategy = .custom { decoder in
                    let value = try decoder.singleValueContainer().decode(String.self)
                    let parser = ISO8601DateFormatter()
                    parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
                    guard let date = parser.date(from: value) else { throw CocoaError(.fileReadCorruptFile) }
                    return date
                }
                let resultData = try decoder.decode(CanvasSnapshot.self, from: Data(value.utf8))
                guard library.data.canvasID == nil || library.data.canvasID == resultData.owner else {
                    message = "현재 계정과 다릅니다. 설정에서 먼저 로그아웃하세요."
                    return
                }
                let partial = resultData.courses.filter { $0.assignments == nil || $0.videos == nil || (library.data.preferences.showAttendance && $0.attendance == nil) }.count
                let received = resultData.courses.reduce(0) { $0 + ($1.assignments?.count ?? 0) + ($1.videos?.count ?? 0) }
                if library.update({ resultData.merge(into: &$0) }) {
                    message = partial > 0 ? "일정 \(received)개를 읽었습니다. \(partial)개 과목의 일부 응답을 받지 못해 기존 기록을 유지했습니다." : "과목 \(resultData.courses.count)개 · 일정 \(received)개 동기화 완료"
                }
            } catch {
                if Task.isCancelled { message = "동기화를 중단했습니다." }
                else if String(describing: error).contains("ACCOUNT_CHANGED") { message = "현재 계정과 다릅니다. 설정에서 먼저 로그아웃하세요." }
                else { message = "학교 데이터를 읽지 못했습니다. 로그인과 네트워크 연결을 확인하고 다시 시도하세요." }
            }
        }
    }
}

private struct CanvasSnapshot: Decodable {
    struct Course: Decodable {
        let id: String
        let name: String
        let assignments: [Row]?
        let videos: [Row]?
        let attendance: [CalixAttendance]?
    }

    struct Row: Decodable {
        let id: String
        let title: String
        let course: String
        let kind: EventKind
        let due: Date?
        let done: Bool
        let url: URL?
        let feedback: String?

        func event(previous: CalixEvent?) -> CalixEvent {
            CalixEvent(id: id, title: title, course: course, kind: kind, due: due, note: previous?.note ?? "",
                       done: previous?.manualCompletion ?? done, starred: previous?.starred ?? false, remote: true,
                       manualCompletion: previous?.manualCompletion, url: url.flatMap { CanvasBrowser.isCampus($0) ? $0 : nil }, feedback: feedback)
        }
    }

    let owner: String
    let courses: [Course]

    @MainActor func merge(into data: inout CalixData) {
        var events = Dictionary(data.events.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        var attendance = Dictionary(data.attendance.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        for course in courses {
            for row in (course.assignments ?? []) + (course.videos ?? []) { events[row.id] = row.event(previous: events[row.id]) }
            if let rows = course.attendance {
                attendance = attendance.filter { !$0.key.hasPrefix("lesson:\(course.id):") && !$0.key.hasPrefix("item:\(course.id):") }
                for row in rows { attendance[row.id] = row }
            }
        }
        data.events = events.values.sorted { $0.id < $1.id }
        data.attendance = attendance.values.sorted { $0.id < $1.id }
        data.canvasID = owner
        if courses.isEmpty || courses.contains(where: { $0.assignments != nil || $0.videos != nil || $0.attendance != nil }) { data.lastSync = .now }
    }
}
