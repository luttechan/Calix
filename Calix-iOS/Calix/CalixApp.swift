import SwiftUI

@main
struct CalixApp: App {
    var body: some Scene {
        WindowGroup {
            CalixView()
                .environment(\.locale, Locale(identifier: "ko_KR"))
        }
    }
}
