import SwiftUI

struct ContentView: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var recordingStore: RecordingStore

    var body: some View {
        TabView {
            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gearshape")
                }

            HorseSessionView()
                .tabItem {
                    Label("Horse", systemImage: "hare")
                }

            RecordingView()
                .tabItem {
                    Label("Record", systemImage: "waveform.circle")
                }

            UploadView()
                .tabItem {
                    Label("Upload", systemImage: "icloud.and.arrow.up")
                }
        }
    }
}

#Preview {
    ContentView()
        .environmentObject(AppSettings())
        .environmentObject(RecordingStore())
}
