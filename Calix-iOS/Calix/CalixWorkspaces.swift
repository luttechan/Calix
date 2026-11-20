import SwiftUI

struct CalixChecklist: View {
    let library: CalixLibrary
    @State private var editing: CalixTask?
    @State private var search = ""

    var body: some View {
        let visible = library.data.tasks.filter { search.isEmpty || $0.title.localizedCaseInsensitiveContains(search) }
        let groups = Dictionary(grouping: visible, by: \.section)
        List {
            ForEach(groups.keys.sorted(), id: \.self) { section in
                Section(section) {
                    ForEach(groups[section, default: []]) { task in
                        Button {
                            library.update { data in
                                if let index = data.tasks.firstIndex(where: { $0.id == task.id }) { data.tasks[index].done.toggle() }
                            }
                        } label: { Label(task.title, systemImage: task.done ? "checkmark.circle.fill" : "circle") }
                            .swipeActions(edge: .leading) { Button("편집") { editing = task } }
                            .swipeActions {
                                Button("삭제", role: .destructive) { library.update { $0.tasks.removeAll { $0.id == task.id } } }
                            }
                    }
                }
            }
            if groups.isEmpty { ContentUnavailableView("표시할 할 일이 없습니다", systemImage: "checklist") }
        }
        .navigationTitle("체크리스트")
        .searchable(text: $search)
        .toolbar { Button { editing = CalixTask() } label: { Label("할 일 추가", systemImage: "plus") } }
        .sheet(item: $editing) { item in
            EditForm(title: "할 일", initial: item, valid: { !$0.title.trimmed.isEmpty }) { draft in
                TextField("제목", text: draft.title)
                TextField("목록 이름", text: draft.section)
                Toggle("완료", isOn: draft.done)
            } save: { item in
                var item = item
                item.title = item.title.trimmed
                item.section = item.section.trimmed.isEmpty ? "기본" : item.section.trimmed
                return library.update { $0.tasks.replace(item) }
            }
        }
    }
}

struct CalixTimetable: View {
    let library: CalixLibrary
    @Environment(\.scenePhase) private var phase
    @State private var term: String?
    @State private var day = Calendar.current.component(.weekday, from: .now)
    @State private var editing: CalixLesson?
    @State private var offDate = Date()
    @State private var showOffDay = false
    @State private var authorized = false
    @State private var showFree = false
    private let days = ["일", "월", "화", "수", "목", "금", "토"]

    var body: some View {
        let selected = term ?? library.data.preferences.mainTerm
        let terms = Set(library.data.lessons.map(\.term) + [selected, library.data.preferences.mainTerm]).sorted()
        let items = library.data.lessons.filter { $0.term == selected }
        let active = items.filter { $0.weekday == day && !$0.online }.sorted { $0.start < $1.start }
        let online = items.filter(\.online)
        Group {
            if library.data.preferences.lockTimetable && !authorized {
                ProtectedView(library: library, title: "시간표", access: $authorized)
            } else {
                List {
                    Picker("학기", selection: Binding(get: { selected }, set: { term = $0 })) {
                        ForEach(terms, id: \.self) { Text($0).tag($0) }
                    }
                    Picker("요일", selection: $day) {
                        ForEach([2, 3, 4, 5, 6, 7, 1], id: \.self) { index in Text(days[index - 1]).tag(index) }
                    }.pickerStyle(.segmented)
                    Section("\(days[day - 1])요일") {
                        if active.isEmpty { Text("등록된 수업이 없습니다.").foregroundStyle(.secondary) }
                        ForEach(active) { row($0) }
                    }
                    Section("비대면") {
                        if online.isEmpty { Text("등록된 비대면 수업이 없습니다.").foregroundStyle(.secondary) }
                        ForEach(online) { row($0) }
                    }
                    DisclosureGroup("공강 찾기", isExpanded: $showFree) {
                        let intervals = freeSlots(active)
                        if intervals.isEmpty { Text("30분 이상 비어 있는 시간이 없습니다.") }
                        ForEach(intervals, id: \.self) { Text($0).monospacedDigit() }
                    }
                    Button("휴강일 관리") { showOffDay = true }
                    if selected != library.data.preferences.mainTerm {
                        Button("기본 학기로 설정") { library.update { $0.preferences.mainTerm = selected } }
                    }
                }
                .toolbar {
                    Button { editing = CalixLesson(term: selected, weekday: day) } label: { Label("수업 추가", systemImage: "plus") }
                }
            }
        }
        .navigationTitle("시간표")
        .onChange(of: phase) { _, newPhase in if newPhase == .background { authorized = false; editing = nil; showOffDay = false } }
        .sheet(item: $editing) { lesson in
            EditForm(title: "수업 편집", initial: lesson, valid: { !$0.title.trimmed.isEmpty && !$0.term.trimmed.isEmpty && ($0.online || $0.start < $0.end) }) { item in
                TextField("수업 이름", text: item.title)
                TextField("학기", text: item.term)
                TextField("교수", text: item.lecturer)
                TextField("강의실", text: item.room)
                Toggle("비대면", isOn: item.online)
                if !item.wrappedValue.online {
                    Picker("요일", selection: item.weekday) {
                        ForEach(1...7, id: \.self) { Text("\(days[$0 - 1])요일").tag($0) }
                    }
                    DatePicker("시작", selection: clock(item.start), displayedComponents: .hourAndMinute)
                    DatePicker("종료", selection: clock(item.end), displayedComponents: .hourAndMinute)
                }
            } save: { item in
                var item = item
                item.title = item.title.trimmed
                item.term = item.term.trimmed
                if library.update({ $0.lessons.replace(item) }) { term = item.term; day = item.weekday; return true }
                return false
            }
        }
        .sheet(isPresented: $showOffDay) {
            NavigationStack {
                Form {
                    DatePicker("날짜", selection: $offDate, displayedComponents: .date)
                    let key = CalixData.dayKey(offDate)
                    if library.data.offDays[key] == nil {
                        Button("휴강일로 지정") { library.update { $0.offDays[key] = "휴강" } }
                    } else {
                        Button("휴강일 지정 해제") { library.update { $0.offDays[key] = nil } }
                    }
                }
                .navigationTitle("휴강일")
                .toolbar { Button("닫기") { showOffDay = false } }
            }
        }
    }

    private func row(_ item: CalixLesson) -> some View {
        Button { editing = item } label: {
            VStack(alignment: .leading, spacing: 4) {
                Text(item.title).foregroundStyle(.primary)
                if !item.online { Text("\(time(item.start))–\(time(item.end))").monospacedDigit() }
                Text([item.room, item.lecturer].filter { !$0.isEmpty }.joined(separator: " · ")).foregroundStyle(.secondary)
            }
        }
        .swipeActions { Button("삭제", role: .destructive) { library.update { $0.lessons.removeAll { $0.id == item.id } } } }
    }

    private func clock(_ minutes: Binding<Int>) -> Binding<Date> {
        Binding(get: {
            Calendar.current.date(bySettingHour: minutes.wrappedValue / 60, minute: minutes.wrappedValue % 60, second: 0, of: .now) ?? .now
        }, set: { date in
            let parts = Calendar.current.dateComponents([.hour, .minute], from: date)
            minutes.wrappedValue = (parts.hour ?? 0) * 60 + (parts.minute ?? 0)
        })
    }

    private func time(_ minutes: Int) -> String { String(format: "%02d:%02d", minutes / 60, minutes % 60) }

    private func freeSlots(_ active: [CalixLesson]) -> [String] {
        var cursor = 8 * 60
        let closing = 20 * 60
        var result: [String] = []
        for lesson in active where lesson.end > cursor && lesson.start < closing {
            if lesson.start - cursor >= 30 { result.append("\(time(cursor))–\(time(lesson.start))") }
            cursor = max(cursor, lesson.end)
        }
        if closing - cursor >= 30 { result.append("\(time(cursor))–\(time(closing))") }
        return result
    }
}

struct CalixGrades: View {
    let library: CalixLibrary
    @Environment(\.scenePhase) private var phase
    @State private var authorized = false
    @State private var term: String?
    @State private var editing: CalixGrade?
    @State private var search = ""

    var body: some View {
        let selected = term ?? library.data.preferences.mainTerm
        let scale = library.data.preferences.gradeScale
        let items = library.data.grades.filter { $0.term == selected }
        let terms = Set(library.data.grades.map(\.term) + [selected, library.data.preferences.mainTerm]).sorted()
        let credits = items.filter { gradePoints($0.mark, scale: scale) != nil }.reduce(0.0) { $0 + $1.credits }
        let points = items.reduce(0.0) { $0 + (gradePoints($1.mark, scale: scale) ?? 0) * $1.credits }
        Group {
            if authorized {
                List {
                    Picker("학기", selection: Binding(get: { selected }, set: { term = $0 })) {
                        ForEach(terms, id: \.self) { Text($0).tag($0) }
                    }
                    Picker("평점 기준", selection: Binding(get: { scale }, set: { value in library.update { $0.preferences.gradeScale = value } })) {
                        ForEach([4.5, 4.3, 4.0], id: \.self) { Text($0.formatted(.number.precision(.fractionLength(1)))).tag($0) }
                    }
                    LabeledContent("평균 평점", value: credits > 0 ? (points / credits).formatted(.number.precision(.fractionLength(2))) : "–")
                    LabeledContent("등록 학점", value: items.reduce(0.0) { $0 + $1.credits }.formatted())
                    ForEach(items.filter { search.isEmpty || $0.title.localizedCaseInsensitiveContains(search) }.sorted { $0.title < $1.title }) { item in
                        Button { editing = item } label: { LabeledContent(item.title, value: "\(item.mark) · \(item.credits.formatted())학점") }
                            .swipeActions { Button("삭제", role: .destructive) { library.update { $0.grades.removeAll { $0.id == item.id } } } }
                    }
                }
                .searchable(text: $search, prompt: "과목 검색")
                .toolbar { Button { editing = CalixGrade(term: selected) } label: { Label("과목 추가", systemImage: "plus") } }
            } else {
                ProtectedView(library: library, title: "학점 계산기", access: $authorized)
            }
        }
        .navigationTitle("학점 계산기")
        .onChange(of: phase) { _, value in if value == .background { authorized = false; editing = nil } }
        .sheet(item: $editing) { item in
            EditForm(title: "학점 편집", initial: item, valid: { !$0.title.trimmed.isEmpty && !$0.term.trimmed.isEmpty }) { draft in
                TextField("과목", text: draft.title)
                TextField("학기", text: draft.term)
                Stepper("\(draft.wrappedValue.credits.formatted())학점", value: draft.credits, in: 0...30, step: 0.5)
                Picker("성적", selection: draft.mark) {
                    ForEach(gradeMarks, id: \.self) { Text($0).tag($0) }
                }
            } save: { item in
                var item = item
                item.title = item.title.trimmed
                item.term = item.term.trimmed
                if library.update({ $0.grades.replace(item) }) { term = item.term; return true }
                return false
            }
        }
    }
}

private let gradeMarks = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F", "P", "NP"]

private func gradePoints(_ mark: String, scale: Double) -> Double? {
    guard let index = gradeMarks.firstIndex(of: mark), index < 13 else { return nil }
    switch scale {
    case 4.5: return [4.5, 4, 4, 3.5, 3, 3, 2.5, 2, 2, 1.5, 1, 1, 0][index]
    case 4.3: return [4.3, 4, 3.7, 3.3, 3, 2.7, 2.3, 2, 1.7, 1.3, 1, 0.7, 0][index]
    default: return [4, 4, 3.7, 3.3, 3, 2.7, 2.3, 2, 1.7, 1.3, 1, 0.7, 0][index]
    }
}

struct ProtectedView: View {
    let library: CalixLibrary
    let title: String
    @Binding var access: Bool

    var body: some View {
        ContentUnavailableView {
            Label(title, systemImage: "lock")
        } actions: {
            Button("잠금 해제") {
                Task { access = await library.authenticate("\(title)을 열려면 인증하세요.") }
            }.buttonStyle(.borderedProminent)
        }
    }
}

struct EditForm<Value, Fields: View>: View {
    let title: String
    @State private var value: Value
    let valid: (Value) -> Bool
    let fields: (Binding<Value>) -> Fields
    let save: (Value) -> Bool
    @Environment(\.dismiss) private var dismiss

    init(title: String, initial: Value, valid: @escaping (Value) -> Bool,
         @ViewBuilder fields: @escaping (Binding<Value>) -> Fields, save: @escaping (Value) -> Bool) {
        self.title = title
        _value = State(initialValue: initial)
        self.valid = valid
        self.fields = fields
        self.save = save
    }

    var body: some View {
        NavigationStack {
            Form { fields($value) }
                .navigationTitle(title)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("취소") { dismiss() } }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("저장") { if save(value) { dismiss() } }.disabled(!valid(value))
                    }
                }
        }
    }
}

extension Array where Element: Identifiable {
    mutating func replace(_ item: Element) {
        if let index = firstIndex(where: { $0.id == item.id }) { self[index] = item }
        else { append(item) }
    }
}

extension String {
    var trimmed: String { trimmingCharacters(in: .whitespacesAndNewlines) }
}
