import SwiftUI

struct CalixRoot: View {
    let library: CalixLibrary
    @Environment(\.scenePhase) private var phase
    #if DEBUG
    @State private var tab = CalixScreenshot.tab
    #else
    @State private var tab = 0
    #endif

    var body: some View {
        Group {
            if library.unavailable {
                ContentUnavailableView {
                    Label("Calix", systemImage: "externaldrive.badge.exclamationmark")
                } description: {
                    Text("저장한 데이터를 열지 못했습니다.")
                } actions: {
                    Button("다시 시도") { library.reload() }.buttonStyle(.borderedProminent)
                }
            } else if library.locked {
                ContentUnavailableView {
                    Label("Calix 잠김", systemImage: "lock.fill")
                } actions: {
                    Button("잠금 해제") {
                        Task {
                            if await library.authenticate("Calix 잠금을 해제합니다.") {
                                library.locked = false
                                library.finishFocusIfNeeded()
                            }
                        }
                    }.buttonStyle(.borderedProminent)
                }
            } else {
                TabView(selection: $tab) {
                    NavigationStack { CalixHome(library: library, openDeadlines: { tab = 1 }) }
                        .tabItem { Label("홈", systemImage: "house") }.tag(0)
                    NavigationStack { CalixEvents(library: library) }
                        .tabItem { Label("일정", systemImage: "calendar.badge.clock") }.tag(1)
                    NavigationStack { CalixCalendar(library: library) }
                        .tabItem { Label("달력", systemImage: "calendar") }.tag(2)
                    NavigationStack { CalixCourseList(library: library) }
                        .tabItem { Label("과목", systemImage: "books.vertical") }.tag(3)
                    NavigationStack { CalixMore(library: library) }
                        .tabItem { Label("더 보기", systemImage: "ellipsis") }.tag(4)
                }
            }
        }
        .tint(Color(hue: library.data.preferences.theme.hue, saturation: 0.55, brightness: 0.76))
        .preferredColorScheme(library.data.preferences.theme == .dark ? .dark : nil)
        .overlay {
            if phase == .background && library.data.preferences.lockOnBackground {
                Rectangle().fill(.background).ignoresSafeArea()
            }
        }
        .alert("Calix", isPresented: Binding(get: { library.issue != nil }, set: { if !$0 { library.issue = nil } })) {
            Button("확인", role: .cancel) { library.issue = nil }
        } message: {
            Text(library.issue ?? "")
        }
    }
}

struct CalixHome: View {
    let library: CalixLibrary
    let openDeadlines: () -> Void

    var body: some View {
        TimelineView(.periodic(from: .now, by: 30)) { context in
            let now = context.date
            let pending = library.data.events.filter { !$0.done }
            let today = pending.filter { DeadlineGroup.classify($0.due, now: now) == .today }.ordered
            let overdue = pending.filter { DeadlineGroup.classify($0.due, now: now) == .overdue }.ordered
            let upcoming = pending.filter { DeadlineGroup.classify($0.due, now: now) == .week }.ordered
            List {
                Section {
                    HomeScheduleCard(date: now, preference: library.data.preferences, today: today.count, overdue: overdue.count, openDeadlines: openDeadlines)
                        .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                }
                Section("오늘의 학습 계획") {
                    if today.count + overdue.count >= 3 {
                        Label("오늘 마감과 기한 경과 일정이 몰려 있습니다.", systemImage: "exclamationmark.triangle")
                    }
                    if today.isEmpty && overdue.isEmpty { Text("오늘 확인할 일정이 없습니다.").foregroundStyle(.secondary) }
                    ForEach((overdue + today).prefix(5)) { EventLink(id: $0.id, library: library) }
                }
                Section {
                    NavigationLink {
                        CalixCanvas(library: library)
                    } label: {
                        Label {
                            VStack(alignment: .leading, spacing: 5) {
                                Text(library.data.canvasID == nil ? "학교 계정 연결" : "학교 동기화")
                                Text(library.data.lastSync.map { "최근 동기화 " + $0.formatted(.dateTime.month().day().hour().minute()) } ?? "Canvas 과제·영상·출결 가져오기")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                        } icon: { Image(systemName: "arrow.triangle.2.circlepath") }
                    }
                }
                Section("다가오는 일정") {
                    if upcoming.isEmpty { Text("7일 이내 마감 일정이 없습니다.").foregroundStyle(.secondary) }
                    ForEach(upcoming.prefix(5)) { EventLink(id: $0.id, library: library) }
                }
            }
        }
        .navigationTitle("Calix")
        .toolbar { NavigationLink { CalixCanvas(library: library) } label: { Label("학교 동기화", systemImage: "arrow.triangle.2.circlepath") } }
    }
}

private struct HomeScheduleCard: View {
    let date: Date
    let preference: CalixPreferences
    let today: Int
    let overdue: Int
    let openDeadlines: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            Label(date.formatted(.dateTime.month().day().weekday()), systemImage: "calendar")
                .font(.footnote.weight(.semibold)).foregroundStyle(.white.opacity(0.86))
            if !preference.nickname.isEmpty { Text("\(preference.nickname)님").font(.subheadline.weight(.medium)) }
            Text(preference.homeMessage).font(.title2.bold()).accessibilityAddTraits(.isHeader)
            HStack(spacing: 12) {
                metric("오늘 마감", today, "clock")
                metric("기한 경과", overdue, "exclamationmark.circle")
            }
            Button(action: openDeadlines) { Label("마감 보드 열기", systemImage: "arrow.right") }
                .buttonStyle(.borderedProminent)
                .foregroundStyle(Color(red: 0.22, green: 0.14, blue: 0.42))
                .tint(.white)
        }
        .padding(21)
        .frame(maxWidth: .infinity, alignment: .leading)
        .foregroundStyle(.white)
        .background {
            RoundedRectangle(cornerRadius: 24).fill(LinearGradient(colors: [
                Color(hue: preference.theme.hue, saturation: 0.63, brightness: 0.51),
                Color(hue: preference.theme.hue - 0.04, saturation: 0.49, brightness: 0.40)
            ], startPoint: .topLeading, endPoint: .bottomTrailing))
        }
    }

    private func metric(_ title: String, _ count: Int, _ symbol: String) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Label(title, systemImage: symbol).font(.footnote)
            Text(count.formatted()).font(.title2.weight(.semibold).monospacedDigit())
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(.white.opacity(0.13), in: RoundedRectangle(cornerRadius: 13))
        .accessibilityElement(children: .combine)
    }
}

struct CalixEvents: View {
    let library: CalixLibrary
    @State private var search = ""
    @State private var kind: EventKind?
    @State private var showCompleted = false
    @State private var starredOnly = false
    @State private var adding = false

    var body: some View {
        TimelineView(.periodic(from: .now, by: 30)) { context in
            let visible = library.data.events.filter {
                (showCompleted || !$0.done) && (!starredOnly || $0.starred) && (kind == nil || kind == $0.kind) &&
                    (search.isEmpty || "\($0.title) \($0.course)".localizedCaseInsensitiveContains(search))
            }.ordered
            List {
                ForEach(DeadlineGroup.allCases) { group in
                    let items = visible.filter { DeadlineGroup.classify($0.due, now: context.date) == group }
                    if !items.isEmpty {
                        Section("\(group.rawValue) · \(items.count)개") {
                            ForEach(items) { EventLink(id: $0.id, library: library) }
                        }
                    }
                }
                if visible.isEmpty { ContentUnavailableView("표시할 일정이 없습니다", systemImage: "calendar") }
            }
        }
        .navigationTitle("마감 보드")
        .searchable(text: $search, prompt: "일정·과목 검색")
        .toolbar {
            Menu {
                Picker("일정 종류", selection: $kind) {
                    Text("전체").tag(nil as EventKind?)
                    ForEach(EventKind.allCases) { Text($0.rawValue).tag(Optional($0)) }
                }
                Toggle("완료 일정 포함", isOn: $showCompleted)
                Toggle("별표만 표시", isOn: $starredOnly)
            } label: { Label("필터", systemImage: "line.3.horizontal.decrease.circle") }
            Button { adding = true } label: { Label("일정 추가", systemImage: "plus") }
        }
        .sheet(isPresented: $adding) { NavigationStack { EventEditor(library: library, draft: CalixEvent(kind: .personal)) } }
    }
}

struct EventLink: View {
    let id: String
    let library: CalixLibrary

    var body: some View {
        if let event = library.data.events.first(where: { $0.id == id }) {
            NavigationLink {
                EventDetails(id: id, library: library)
            } label: {
                Label {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(event.title)
                        Text([event.course, event.done ? "완료" : event.due?.formatted(.dateTime.month().day().hour().minute()) ?? "기한 없음"].filter { !$0.isEmpty }.joined(separator: " · "))
                            .font(.caption).foregroundStyle(.secondary)
                    }
                } icon: {
                    Image(systemName: event.done ? "checkmark.circle.fill" : event.starred ? "star.fill" : event.kind.symbol)
                }
            }
        }
    }
}

private struct EventDetails: View {
    let id: String
    let library: CalixLibrary
    @Environment(\.dismiss) private var dismiss
    @State private var editing = false
    @State private var deleting = false

    var body: some View {
        if let event = library.data.events.first(where: { $0.id == id }) {
            Form {
                Section {
                    LabeledContent("과목", value: event.course.isEmpty ? "개인 일정" : event.course)
                    LabeledContent("유형", value: event.kind.rawValue)
                    LabeledContent("마감", value: event.due?.formatted(.dateTime.month().day().hour().minute()) ?? "기한 없음")
                    if let url = event.url { Link("Canvas에서 열기", destination: url) }
                    if let feedback = event.feedback { Text(feedback) }
                    if !event.note.isEmpty { Text(event.note) }
                }
                Section {
                    Button(event.done ? "완료 취소" : "완료로 표시") {
                        change { item in
                            item.done.toggle()
                            if item.remote { item.manualCompletion = item.done }
                        }
                    }
                    Button(event.starred ? "별표 해제" : "별표 표시") { change { $0.starred.toggle() } }
                    if !event.remote { Button("일정 삭제", role: .destructive) { deleting = true } }
                }
            }
            .navigationTitle(event.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { Button("편집") { editing = true } }
            .sheet(isPresented: $editing) { NavigationStack { EventEditor(library: library, draft: event) } }
            .confirmationDialog("이 일정을 삭제할까요?", isPresented: $deleting, titleVisibility: .visible) {
                Button("삭제", role: .destructive) {
                    if library.update({ $0.events.removeAll { $0.id == id } }) { dismiss() }
                }
                if let series = event.seriesID {
                    Button("반복 일정 전체 삭제", role: .destructive) {
                        if library.update({ $0.events.removeAll { $0.seriesID == series } }) { dismiss() }
                    }
                }
            }
        }
    }

    private func change(_ edit: (inout CalixEvent) -> Void) {
        library.update { draft in
            if let index = draft.events.firstIndex(where: { $0.id == id }) { edit(&draft.events[index]) }
        }
    }
}

struct EventEditor: View {
    let library: CalixLibrary
    @State var draft: CalixEvent
    @State private var copies = 1
    @State private var interval = 7
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        Form {
            Section("일정") {
                if draft.remote { Text(draft.title) } else {
                    TextField("제목", text: $draft.title)
                    TextField("과목", text: $draft.course)
                    Picker("유형", selection: $draft.kind) { ForEach(EventKind.allCases) { Text($0.rawValue).tag($0) } }
                    Toggle("마감 설정", isOn: Binding(get: { draft.due != nil }, set: { draft.due = $0 ? .now : nil }))
                    if draft.due != nil {
                        DatePicker("마감", selection: Binding(get: { draft.due ?? .now }, set: { draft.due = $0 }))
                        if !library.data.events.contains(where: { $0.id == draft.id }) {
                            Stepper("반복 횟수 \(copies)회", value: $copies, in: 1...52)
                            if copies > 1 {
                                Picker("반복 간격", selection: $interval) {
                                    Text("매일").tag(1)
                                    Text("매주").tag(7)
                                    Text("격주").tag(14)
                                }
                            }
                        }
                    }
                }
                TextField("메모", text: $draft.note, axis: .vertical)
            }
        }
        .navigationTitle("일정 편집")
        .toolbar {
            ToolbarItem(placement: .cancellationAction) { Button("취소") { dismiss() } }
            ToolbarItem(placement: .confirmationAction) {
                Button("저장") {
                    draft.title = draft.title.trimmingCharacters(in: .whitespacesAndNewlines)
                    if library.update({ data in
                        if let index = data.events.firstIndex(where: { $0.id == draft.id }) {
                            if draft.remote { data.events[index].note = draft.note }
                            else { data.events[index] = draft }
                        } else if !draft.remote {
                            guard copies > 1, let date = draft.due else { data.events.append(draft); return }
                            let series = UUID().uuidString
                            for index in 0..<copies {
                                guard let due = Calendar.current.date(byAdding: .day, value: index * interval, to: date) else { continue }
                                var item = draft
                                item.id = index == 0 ? draft.id : UUID().uuidString
                                item.due = due
                                item.seriesID = series
                                data.events.append(item)
                            }
                        }
                    }) { dismiss() }
                }.disabled(draft.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
    }
}

struct CalixCourseList: View {
    let library: CalixLibrary
    @State private var search = ""
    @State private var pendingOnly = false

    var body: some View {
        let groups = Dictionary(grouping: library.data.events) { $0.course.isEmpty ? "개인 일정" : $0.course }
        let names = groups.keys.sorted { $0.localizedCompare($1) == .orderedAscending }.filter { name in
            (search.isEmpty || name.localizedCaseInsensitiveContains(search)) &&
                (!pendingOnly || groups[name, default: []].contains { !$0.done })
        }
        List {
            Toggle("미완료 있는 과목", isOn: $pendingOnly)
            ForEach(names, id: \.self) { name in
                let events = groups[name, default: []].ordered
                let done = events.filter(\.done).count
                Section(name) {
                    ProgressView(value: Double(done), total: Double(max(1, events.count))) { Text("완료 \(done)/\(events.count)") }
                    ForEach(events) { EventLink(id: $0.id, library: library) }
                }
            }
            if names.isEmpty { ContentUnavailableView("표시할 과목이 없습니다", systemImage: "books.vertical") }
        }
        .navigationTitle("과목별 현황")
        .searchable(text: $search, prompt: "과목 검색")
    }
}

struct CalixCalendar: View {
    let library: CalixLibrary
    @State private var date = Date()
    @State private var holiday = ""
    @State private var editingHoliday = false
    @State private var adding = false

    var body: some View {
        let key = CalixData.dayKey(date)
        let events = library.data.events.filter { $0.due.map { Calendar.current.isDate($0, inSameDayAs: date) } ?? false }.ordered
        List {
            DatePicker("날짜", selection: $date, displayedComponents: .date).datePickerStyle(.graphical)
            Section {
                if let name = library.data.holidays[key] { Label(name, systemImage: "calendar.badge.checkmark") }
                if let name = library.data.offDays[key] { Label(name, systemImage: "moon.zzz") }
                if events.isEmpty { Text("선택한 날짜에 마감할 일정이 없습니다.").foregroundStyle(.secondary) }
                ForEach(events) { EventLink(id: $0.id, library: library) }
            } header: { Text(date.formatted(.dateTime.month().day().weekday())) }
            Button("휴일 이름 편집") { holiday = library.data.holidays[key] ?? ""; editingHoliday = true }
        }
        .navigationTitle("달력")
        .toolbar { Button { adding = true } label: { Label("일정 추가", systemImage: "plus") } }
        .alert("휴일 이름", isPresented: $editingHoliday) {
            TextField("이름", text: $holiday)
            Button("저장") { library.update { $0.holidays[key] = holiday.isEmpty ? nil : holiday } }
            Button("취소", role: .cancel) {}
        }
        .sheet(isPresented: $adding) { NavigationStack { EventEditor(library: library, draft: CalixEvent(kind: .personal, due: date)) } }
    }
}

private extension Array where Element == CalixEvent {
    var ordered: Self {
        sorted { a, b in
            let earlier = a.due ?? .distantFuture
            let later = b.due ?? .distantFuture
            return earlier == later ? a.title.localizedCompare(b.title) == .orderedAscending : earlier < later
        }
    }
}
