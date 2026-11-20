import PhotosUI
import SwiftUI
import UniformTypeIdentifiers

struct CalixMore: View {
    let library: CalixLibrary

    var body: some View {
        List {
            Section("학습") {
                destination("시간표", "rectangle.split.3x3") { CalixTimetable(library: library) }
                destination("체크리스트", "checklist") { CalixChecklist(library: library) }
                destination("학점 계산기", "graduationcap") { CalixGrades(library: library) }
                if library.data.preferences.showAttendance {
                    destination("출결", "checkmark.seal") { CalixAttendanceList(library: library) }
                }
                destination("학교 동기화", "arrow.triangle.2.circlepath") { CalixCanvas(library: library) }
            }
            Section("기록") {
                destination("집중 타이머", "timer") { CalixStudy(library: library) }
                destination("일기장", "book.closed") { CalixDiary(library: library, secret: false) }
                destination("비밀 일기", "lock.doc") { CalixDiary(library: library, secret: true) }
            }
            Section("Calix") {
                destination("설정", "gearshape") { CalixSettings(library: library) }
                Button { library.locked = true } label: { Label("지금 잠금", systemImage: "lock") }
                    .disabled(!library.data.preferences.lockOnBackground)
            }
        }
        .navigationTitle("더 보기")
    }

    private func destination<Content: View>(_ title: String, _ symbol: String, @ViewBuilder content: () -> Content) -> some View {
        NavigationLink(destination: content) { Label(title, systemImage: symbol) }
    }
}

private struct CalixAttendanceList: View {
    let library: CalixLibrary
    @State private var filter: String?
    private let labels = ["attendance": "출석", "late": "지각", "absent": "결석", "excused": "공결", "none": "미확인"]

    var body: some View {
        let groups = Dictionary(grouping: library.data.attendance, by: \.course)
        let names = groups.keys.sorted()
        List {
            if names.isEmpty {
                ContentUnavailableView("출결 기록이 없습니다", systemImage: "checkmark.seal", description: Text("학교 동기화에서 출결 정보를 가져오세요."))
            } else {
                Picker("과목", selection: $filter) {
                    Text("전체").tag(nil as String?)
                    ForEach(names, id: \.self) { Text($0).tag(Optional($0)) }
                }
                ForEach(names.filter { filter == nil || filter == $0 }, id: \.self) { course in
                    Section(course) {
                        ForEach(groups[course, default: []].sorted { ($0.date ?? .distantFuture) < ($1.date ?? .distantFuture) }) { row in
                            LabeledContent {
                                Text(labels[row.status] ?? "미확인")
                            } label: {
                                VStack(alignment: .leading) {
                                    Text(row.title)
                                    if let date = row.date { Text(date.formatted(.dateTime.month().day())).font(.caption).foregroundStyle(.secondary) }
                                }
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle("출결")
    }
}

private struct CalixDiary: View {
    let library: CalixLibrary
    let secret: Bool
    @Environment(\.scenePhase) private var phase
    @State private var access = false
    @State private var editing: CalixJournal?
    @State private var search = ""

    var body: some View {
        let title = secret ? "비밀 일기" : "일기장"
        Group {
            if secret && !access {
                ProtectedView(library: library, title: title, access: $access)
            } else {
                let entries = library.data.journals.filter {
                    $0.secret == secret && (search.isEmpty || "\($0.title) \($0.body)".localizedCaseInsensitiveContains(search))
                }.sorted { $0.date > $1.date }
                List {
                    ForEach(entries) { entry in
                        Button { editing = entry } label: {
                            VStack(alignment: .leading, spacing: 5) {
                                Text(entry.title.isEmpty ? "제목 없음" : entry.title).foregroundStyle(.primary)
                                Text(entry.date.formatted(.dateTime.year().month().day())).font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        .swipeActions { Button("삭제", role: .destructive) { library.update { $0.journals.removeAll { $0.id == entry.id } } } }
                    }
                    if entries.isEmpty { ContentUnavailableView("일기가 없습니다", systemImage: "book.closed") }
                }
                .searchable(text: $search, prompt: "일기 검색")
                .toolbar { Button { editing = CalixJournal(secret: secret) } label: { Label("일기 작성", systemImage: "square.and.pencil") } }
            }
        }
        .navigationTitle(title)
        .onChange(of: phase) { _, value in if value == .background && secret { access = false; editing = nil; search = "" } }
        .sheet(item: $editing) { entry in
            EditForm(title: title, initial: entry, valid: { !$0.title.trimmed.isEmpty || !$0.body.trimmed.isEmpty }) { item in
                DatePicker("날짜", selection: item.date, displayedComponents: .date)
                TextField("제목", text: item.title)
                TextEditor(text: item.body).frame(minHeight: 220).accessibilityLabel("일기 본문")
            } save: { entry in
                library.update { $0.journals.replace(entry) }
            }
        }
    }
}

private struct CalixStudy: View {
    let library: CalixLibrary
    @State private var minutes = 25

    var body: some View {
        TimelineView(.periodic(from: .now, by: 1)) { context in
            let focus = library.data.focus
            let elapsed = focus.map { max(0, Int(context.date.timeIntervalSince($0.started))) } ?? 0
            let remaining = focus?.seconds.map { max(0, $0 - elapsed) } ?? elapsed
            let week = Calendar.current.dateInterval(of: .weekOfYear, for: context.date)
            let sessions = library.data.focusHistory.filter { week?.contains($0.started) == true }.sorted { $0.started > $1.started }
            List {
                Section {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(library.data.preferences.focusMessage)
                        Text(String(format: "%02d:%02d", remaining / 60, remaining % 60))
                            .font(.system(size: 48, weight: .semibold, design: .rounded)).monospacedDigit()
                        if focus != nil {
                            Button("집중 종료") { library.stopFocus() }.buttonStyle(.borderedProminent)
                        }
                    }.padding(.vertical, 10)
                }
                if focus == nil {
                    Section("새 집중 세션") {
                        Stepper("뽀모도로 \(minutes)분", value: $minutes, in: 5...120, step: 5)
                        Button("뽀모도로 시작") { library.startFocus(seconds: minutes * 60) }
                        Button("자유 집중 시작") { library.startFocus(seconds: nil) }
                    }
                }
                Section("이번 주 집중 기록") {
                    LabeledContent("합계", value: "\(sessions.reduce(0) { $0 + $1.seconds } / 60)분")
                    ForEach(sessions) { row in
                        LabeledContent(row.started.formatted(.dateTime.month().day().hour().minute()), value: "\(row.seconds / 60)분 \(row.seconds % 60)초")
                    }
                }
            }
            .onChange(of: context.date) { _, now in library.finishFocusIfNeeded(now) }
        }
        .navigationTitle("집중 타이머")
    }
}

private struct CalixSettings: View {
    let library: CalixLibrary
    @State private var avatar: PhotosPickerItem?
    @State private var editingProfile = false
    @State private var confirmSignOut = false
    @State private var confirmReset = false
    @State private var backupExport = false
    @State private var backupImport = false
    @State private var backupDocument: CalixBackup?
    @State private var about = false

    var body: some View {
        Form {
            Section("프로필") {
                HStack(spacing: 16) {
                    Group {
                        if let bytes = library.data.avatar, let photo = UIImage(data: bytes) {
                            Image(uiImage: photo).resizable().scaledToFill()
                        } else {
                            Image(systemName: "person.crop.circle.fill").resizable().scaledToFit().foregroundStyle(.tint)
                        }
                    }.frame(width: 56, height: 56).clipShape(Circle())
                    VStack(alignment: .leading) {
                        Button(library.data.preferences.nickname.isEmpty ? "프로필 편집" : library.data.preferences.nickname) { editingProfile = true }
                        PhotosPicker(selection: $avatar, matching: .images) { Text("사진 변경").font(.subheadline) }
                    }
                }
                if library.data.avatar != nil { Button("사진 지우기") { library.update { $0.avatar = nil } } }
            }
            Section("화면") {
                Picker("테마", selection: setting(\.theme)) { ForEach(CalixTheme.allCases) { Text($0.rawValue).tag($0) } }
                Toggle("출결 표시 및 동기화", isOn: setting(\.showAttendance))
            }
            Section("보안") {
                Toggle("앱을 나갈 때 잠금", isOn: lockSetting(\.lockOnBackground))
                Toggle("시간표 잠금", isOn: lockSetting(\.lockTimetable))
            }
            Section("알림") {
                Toggle("마감 알림", isOn: Binding(get: { library.data.preferences.notify }, set: { enabled in Task { await library.setReminders(enabled) } }))
                Picker("알림 시점", selection: setting(\.notifyMinutes)) {
                    ForEach([10, 30, 60, 120, 1440], id: \.self) { Text("\($0)분 전").tag($0) }
                }.disabled(!library.data.preferences.notify)
                Toggle("알림 소리", isOn: setting(\.notifySound))
            }
            Section("학교 계정") {
                NavigationLink("학교 동기화") { CalixCanvas(library: library) }
                if library.data.canvasID != nil { Button("로그아웃", role: .destructive) { confirmSignOut = true } }
            }
            Section("데이터 관리") {
                Button("iOS 데이터 백업") { exportBackup() }
                Button("iOS 백업 가져오기") { backupImport = true }
                Button("기기 데이터 초기화", role: .destructive) { confirmReset = true }
            }
            Section("앱 정보") {
                Button("Calix iOS \(Self.version)") { about = true }
                if let url = URL(string: "https://luttechan.github.io/calix/") { Link("Calix 홈페이지", destination: url) }
            }
        }
        .navigationTitle("설정")
        .task(id: avatar) { await applyAvatar() }
        .sheet(isPresented: $editingProfile) {
            EditForm(title: "프로필", initial: library.data.preferences, valid: { !$0.homeMessage.trimmed.isEmpty }) { item in
                TextField("닉네임", text: item.nickname)
                TextField("홈 문구", text: item.homeMessage)
                TextField("집중 시작 문구", text: item.focusMessage)
                TextField("집중 완료 문구", text: item.focusDoneMessage)
            } save: { prefs in
                library.update {
                    $0.preferences.nickname = String(prefs.nickname.trimmed.prefix(60))
                    $0.preferences.homeMessage = String(prefs.homeMessage.trimmed.prefix(120))
                    $0.preferences.focusMessage = String(prefs.focusMessage.trimmed.prefix(120))
                    $0.preferences.focusDoneMessage = String(prefs.focusDoneMessage.trimmed.prefix(120))
                }
            }
        }
        .fileExporter(isPresented: $backupExport, document: backupDocument, contentType: .json, defaultFilename: "Calix-iOS-Backup") { result in
            backupDocument = nil
            if case .failure = result { library.issue = "백업을 저장하지 못했습니다." }
        }
        .fileImporter(isPresented: $backupImport, allowedContentTypes: [.json]) { result in restoreBackup(result) }
        .confirmationDialog("학교 계정에서 로그아웃할까요?", isPresented: $confirmSignOut, titleVisibility: .visible) {
            Button("로그아웃하고 학교 데이터 지우기", role: .destructive) {
                if library.update({ data in
                    data.canvasID = nil; data.lastSync = nil; data.events.removeAll(where: \.remote); data.attendance.removeAll()
                }) { Task { await CanvasBrowser.clearSession() } }
            }
        } message: { Text("이 기기에 동기화된 학교 일정과 출결이 지워집니다.") }
        .confirmationDialog("이 기기의 Calix 데이터를 초기화할까요?", isPresented: $confirmReset, titleVisibility: .visible) {
            Button("전체 초기화", role: .destructive) {
                if library.update({ $0 = CalixData() }) { Task { await CanvasBrowser.clearSession() }; library.refreshReminders() }
            }
        }
        .alert("Calix iOS \(Self.version)", isPresented: $about) { Button("닫기", role: .cancel) {} }
        message: { Text("Lutein Studio\n부산외대 Canvas 일정 관리") }
    }

    static var version: String { Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0.1.0" }

    private func setting<Value>(_ key: WritableKeyPath<CalixPreferences, Value>) -> Binding<Value> {
        Binding(get: { library.data.preferences[keyPath: key] }, set: { value in library.update { $0.preferences[keyPath: key] = value } })
    }

    private func lockSetting(_ key: WritableKeyPath<CalixPreferences, Bool>) -> Binding<Bool> {
        Binding(get: { library.data.preferences[keyPath: key] }, set: { enabled in
            Task {
                if await library.authenticate("Calix 잠금 설정을 변경합니다.") {
                    library.update { $0.preferences[keyPath: key] = enabled }
                }
            }
        })
    }

    private func applyAvatar() async {
        guard let item = avatar else { return }
        guard let bytes = try? await item.loadTransferable(type: Data.self), bytes.count < 20_000_000,
              let source = UIImage(data: bytes), source.size.width > 0, source.size.height > 0 else {
            library.issue = "사진을 읽지 못했습니다."
            return
        }
        let ratio = min(1, 320 / max(source.size.width, source.size.height))
        let size = CGSize(width: source.size.width * ratio, height: source.size.height * ratio)
        let image = UIGraphicsImageRenderer(size: size).image { _ in source.draw(in: CGRect(origin: .zero, size: size)) }
        library.update { $0.avatar = image.jpegData(compressionQuality: 0.85) }
    }

    private func exportBackup() {
        do {
            var exported = library.data
            exported.events.removeAll(where: \.remote)
            exported.journals.removeAll(where: \.secret)
            exported.grades.removeAll()
            exported.attendance.removeAll()
            exported.canvasID = nil
            exported.lastSync = nil
            exported.focus = nil
            backupDocument = try CalixBackup(contents: JSONEncoder().encode(exported))
            backupExport = true
        } catch { library.issue = "백업을 준비하지 못했습니다." }
    }

    private func restoreBackup(_ result: Result<URL, Error>) {
        do {
            let url = try result.get()
            let accessible = url.startAccessingSecurityScopedResource()
            defer { if accessible { url.stopAccessingSecurityScopedResource() } }
            let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0
            guard size > 0, size < 12_000_000 else { throw CocoaError(.fileReadCorruptFile) }
            let imported = try JSONDecoder().decode(CalixData.self, from: Data(contentsOf: url))
            guard imported.version == 1, imported.lessons.allSatisfy({ (1...7).contains($0.weekday) && (0..<1440).contains($0.start) && (0..<1440).contains($0.end) && ($0.online || $0.start < $0.end) }) else {
                throw CocoaError(.fileReadCorruptFile)
            }
            library.update { data in
                for var item in imported.events where !item.remote { item.url = nil; item.feedback = nil; data.events.replace(item) }
                for item in imported.tasks { data.tasks.replace(item) }
                for item in imported.lessons { data.lessons.replace(item) }
                for item in imported.journals where !item.secret { data.journals.replace(item) }
                for item in imported.focusHistory where item.seconds > 0 { data.focusHistory.replace(item) }
                data.holidays.merge(imported.holidays) { _, latest in latest }
                data.offDays.merge(imported.offDays) { _, latest in latest }
            }
        } catch { library.issue = "Calix iOS 백업을 읽지 못했습니다." }
    }
}

private struct CalixBackup: FileDocument {
    static let readableContentTypes: [UTType] = [.json]
    let contents: Data
    init(contents: Data) { self.contents = contents }
    init(configuration: ReadConfiguration) throws {
        guard let data = configuration.file.regularFileContents else { throw CocoaError(.fileReadCorruptFile) }
        contents = data
    }
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper { FileWrapper(regularFileWithContents: contents) }
}
