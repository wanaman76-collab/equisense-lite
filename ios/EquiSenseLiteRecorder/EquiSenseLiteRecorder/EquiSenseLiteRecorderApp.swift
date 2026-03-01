import SwiftUI

@main
struct EquiSenseLiteRecorderApp: App {
    @StateObject private var settings = AppSettings()
    @StateObject private var recordingStore = RecordingStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(settings)
                .environmentObject(recordingStore)
        }
    }
}
