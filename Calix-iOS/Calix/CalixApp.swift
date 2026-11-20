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
