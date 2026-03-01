import SwiftUI

struct RecordingView: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var recordingStore: RecordingStore

    @State private var motionManager = MotionManager()
    @State private var elapsedTime: TimeInterval = 0
    @State private var timer: Timer?

    private var elapsedFormatted: String {
        let mins = Int(elapsedTime) / 60
        let secs = Int(elapsedTime) % 60
        return String(format: "%02d:%02d", mins, secs)
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Session info
                GroupBox(label: Label("Session Info", systemImage: "info.circle")) {
                    VStack(alignment: .leading, spacing: 8) {
                        if let horse = recordingStore.sessionHorseName {
                            LabeledContent("Horse", value: horse)
                        }
                        if let sid = recordingStore.sessionId {
                            LabeledContent("Session ID", value: String(sid))
                        }
                        if recordingStore.sessionId == nil {
                            Text("No active session. Go to Horse tab first.")
                                .foregroundStyle(.secondary)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(.horizontal)

                // Stats
                HStack(spacing: 32) {
                    VStack {
                        Text(elapsedFormatted)
                            .font(.system(size: 48, weight: .bold, design: .monospaced))
                        Text("Elapsed")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    VStack {
                        Text("\(recordingStore.samples.count)")
                            .font(.system(size: 48, weight: .bold, design: .monospaced))
                        Text("Samples")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                // Record button
                Button {
                    if recordingStore.isRecording {
                        stopRecording()
                    } else {
                        startRecording()
                    }
                } label: {
                    Label(
                        recordingStore.isRecording ? "Stop Recording" : "Start Recording",
                        systemImage: recordingStore.isRecording ? "stop.circle.fill" : "record.circle"
                    )
                    .font(.title2.bold())
                    .foregroundStyle(.white)
                    .padding(.horizontal, 32)
                    .padding(.vertical, 16)
                    .background(recordingStore.isRecording ? Color.red : Color.green,
                                in: RoundedRectangle(cornerRadius: 16))
                }
                .disabled(recordingStore.sessionId == nil)

                if recordingStore.isRecording {
                    HStack {
                        Circle()
                            .fill(.red)
                            .frame(width: 10, height: 10)
                        Text("Recording at 50 Hz")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                Spacer()
            }
            .padding(.top)
            .navigationTitle("Recording")
        }
    }

    private func startRecording() {
        guard let sessionId = recordingStore.sessionId,
              let horseName = recordingStore.sessionHorseName else { return }
        recordingStore.startRecording(sessionId: sessionId, horseName: horseName)
        motionManager.start { sample in
            recordingStore.addSample(sample)
        }
        elapsedTime = 0
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in
            if let start = recordingStore.recordingStartTime {
                elapsedTime = Date().timeIntervalSince(start)
            }
        }
    }

    private func stopRecording() {
        motionManager.stop()
        recordingStore.stopRecording()
        timer?.invalidate()
        timer = nil
    }
}

#Preview {
    RecordingView()
        .environmentObject(AppSettings())
        .environmentObject(RecordingStore())
}
