import SwiftUI

struct CalixView: View {
    private enum Page: String, CaseIterable, Identifiable {
        case home = "홈"
        case deadlines = "마감 보드"
        case courses = "과목별 현황"
        case timetable = "시간표"

        var id: Self { self }
        var symbol: String {
            switch self {
            case .home: "house"
            case .deadlines: "calendar.badge.clock"
            case .courses: "books.vertical"
            case .timetable: "tablecells"
            }
        }
    }

    @AppStorage("demo.anchor") private var savedAnchor: Double = 0
    @AppStorage("demo.completed") private var savedCompletion = "introduction"
    @State private var initialAnchor = Date()
    @State private var page: Page = .home
    @State private var query = ""
    @State private var kind: ScheduleItem.Kind?
    @State private var onlyPending = false
    @State private var weekday = Calendar.current.component(.weekday, from: .now)
    @State private var selectedItem: ScheduleItem?

    private var completed: Set<String> { Set(savedCompletion.split(separator: ",").map(String.init)) }
    private var items: [ScheduleItem] {
        let anchor = savedAnchor == 0 ? initialAnchor : Date(timeIntervalSince1970: savedAnchor)
        return ScheduleItem.sorted(ScheduleItem.samples(startingAt: anchor))
    }

    var body: some View {
        TabView(selection: $page) {
            ForEach(Page.allCases) { destination in
                NavigationStack {
                    Group {
                        switch destination {
                        case .home:
                            TimelineView(.periodic(from: .now, by: 30)) { home(now: $0.date) }
                        case .deadlines:
                            deadlines
                        case .courses:
                            courses
                        case .timetable:
                            timetable
                        }
                    }
                    .navigationTitle(destination == .home ? "Calix" : destination.rawValue)
                    .navigationBarTitleDisplayMode(destination == .home ? .large : .inline)
                }
                .tabItem { Label(destination.rawValue, systemImage: destination.symbol) }
                .tag(destination)
            }
        }
        .onAppear {
            if savedAnchor == 0 { savedAnchor = initialAnchor.timeIntervalSince1970 }
        }
        .sheet(item: $selectedItem) { item in
            NavigationStack {
                itemDetails(item)
                    .navigationTitle("일정 상세")
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .confirmationAction) {
                            Button("닫기") { selectedItem = nil }
                        }
                    }
            }
        }
    }

    private func home(now: Date) -> some View {
        let pending = items.filter { !completed.contains($0.id) }
        let today = pending.filter { DeadlineGroup.classify($0.dueAt, now: now) == .today }
        let overdue = pending.filter { DeadlineGroup.classify($0.dueAt, now: now) == .overdue }
        let upcoming = pending.filter { DeadlineGroup.classify($0.dueAt, now: now) == .week }
        return List {
            Section {
                VStack(alignment: .leading, spacing: 12) {
                    Text(now.formatted(.dateTime.month().day().weekday().locale(Locale(identifier: "ko_KR"))))
                        .font(.subheadline)
                    Text("오늘의 학습 일정")
                        .font(.title2.bold())
                        .accessibilityAddTraits(.isHeader)
                    Text("오늘 마감 \(today.count)개 · 기한 경과 \(overdue.count)개")
                        .font(.subheadline)
                    Button("마감 보드 열기", systemImage: "arrow.right") { page = .deadlines }
                        .buttonStyle(.borderedProminent)
                }
                .foregroundStyle(Color.primary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.vertical, 12)
                .listRowBackground(Color.accentColor.opacity(0.12))
            } header: {
                EmptyView()
            } footer: {
                Label("테스트용 샘플 데이터", systemImage: "iphone")
            }
            Section("오늘 마감") {
                if today.isEmpty { Text("오늘 마감할 일정이 없습니다.").foregroundStyle(.secondary) }
                ForEach(today) { itemRow($0) }
            }
            Section("다가오는 일정") {
                if upcoming.isEmpty { Text("7일 이내 마감 일정이 없습니다.").foregroundStyle(.secondary) }
                ForEach(upcoming.prefix(3)) { itemRow($0) }
            }
        }
    }

    private var deadlines: some View {
        TimelineView(.periodic(from: .now, by: 30)) { context in
            let search = query.trimmingCharacters(in: .whitespacesAndNewlines)
            let visible = items.filter { item in
                !completed.contains(item.id) && (kind == nil || kind == item.kind) &&
                    (search.isEmpty || "\(item.title) \(item.course.name)".localizedCaseInsensitiveContains(search))
            }
            List {
                Picker("일정 종류", selection: $kind) {
                    Text("전체").tag(nil as ScheduleItem.Kind?)
                    ForEach(ScheduleItem.Kind.allCases) { Text($0.rawValue).tag(Optional($0)) }
                }
                .pickerStyle(.segmented)
                .listRowInsets(EdgeInsets())
                .listRowBackground(Color.clear)

                ForEach(DeadlineGroup.allCases) { group in
                    let groupItems = visible.filter { DeadlineGroup.classify($0.dueAt, now: context.date) == group }
                    Section("\(group.rawValue) · \(groupItems.count)개") {
                        if groupItems.isEmpty { Text("일정이 없습니다.").foregroundStyle(.secondary) }
                        ForEach(groupItems) { itemRow($0) }
                    }
                }
            }
        }
        .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: "일정·과목 검색")
    }

    private var courses: some View {
        List {
            Toggle("미완료 있는 과목", isOn: $onlyPending)
            ForEach(Course.samples) { course in
                let courseItems = items.filter { $0.course.id == course.id }
                let pending = courseItems.filter { !completed.contains($0.id) }
                let done = courseItems.count - pending.count
                if !onlyPending || !pending.isEmpty {
                    Section {
                        ProgressView(value: Double(done), total: Double(max(courseItems.count, 1))) {
                            Text("완료 \(done)/\(courseItems.count)")
                        }
                        ForEach(courseItems) { itemRow($0) }
                    } header: {
                        Label(course.name, systemImage: course.symbol)
                    }
                }
            }
            if onlyPending && items.allSatisfy({ completed.contains($0.id) }) {
                Text("모든 과목의 일정을 완료했습니다.").foregroundStyle(.secondary)
            }
        }
    }

    private var timetable: some View {
        let days = [2, 3, 4, 5, 6, 7, 1]
        let koreanNames = ["일", "월", "화", "수", "목", "금", "토"]
        let sessions = ClassSession.samples.filter { $0.weekday == weekday }.sorted { $0.start < $1.start }
        return List {
            Picker("요일", selection: $weekday) {
                ForEach(days, id: \.self) { day in
                    Text(koreanNames[day - 1]).accessibilityLabel("\(koreanNames[day - 1])요일").tag(day)
                }
            }
            .pickerStyle(.segmented)
            .listRowInsets(EdgeInsets())
            .listRowBackground(Color.clear)

            Section("\(koreanNames[weekday - 1])요일 수업") {
                if sessions.isEmpty { Text("예정된 수업이 없습니다.").foregroundStyle(.secondary) }
                ForEach(sessions) { session in
                    VStack(alignment: .leading, spacing: 6) {
                        Label("\(session.start) – \(session.end)", systemImage: "clock")
                            .font(.subheadline.monospacedDigit())
                            .foregroundStyle(Color.accentColor)
                        Text(session.course.name).font(.headline)
                        Text(session.room).font(.subheadline).foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 6)
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }

    private func itemRow(_ item: ScheduleItem) -> some View {
        Button {
            selectedItem = item
        } label: {
            HStack(spacing: 12) {
                Image(systemName: completed.contains(item.id) ? "checkmark.circle.fill" : item.kind.symbol)
                    .foregroundStyle(Color.accentColor)
                    .frame(width: 24)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 4) {
                    Text(item.title).font(.body.weight(.medium)).foregroundStyle(.primary)
                    Text(item.course.name).font(.subheadline).foregroundStyle(.secondary)
                    Text(completed.contains(item.id) ? "완료" : dueLabel(item))
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer(minLength: 4)
                Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary)
                    .accessibilityHidden(true)
            }
            .padding(.vertical, 4)
            .frame(minHeight: 44)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private func itemDetails(_ item: ScheduleItem) -> some View {
        let isComplete = completed.contains(item.id)
        return List {
            Section {
                Text(item.title).font(.title3.bold())
                LabeledContent("과목", value: item.course.name)
                LabeledContent("유형", value: item.kind.rawValue)
                LabeledContent("마감", value: dueLabel(item))
                LabeledContent("상태", value: isComplete ? "완료" : "미완료")
            }
            Button(isComplete ? "완료 취소" : "완료로 표시", systemImage: isComplete ? "arrow.uturn.backward" : "checkmark") {
                var updated = completed
                if isComplete { updated.remove(item.id) } else { updated.insert(item.id) }
                savedCompletion = updated.sorted().joined(separator: ",")
            }
        }
    }

    private func dueLabel(_ item: ScheduleItem) -> String {
        item.dueAt?.formatted(.dateTime.month().day().hour().minute().locale(Locale(identifier: "ko_KR"))) ?? "기한 없음"
    }
}
