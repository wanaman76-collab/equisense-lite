import SwiftUI
import UIKit

struct RecordingView: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var recordingStore: RecordingStore

    @StateObject private var networkMonitor = NetworkMonitor()

    @State private var motionManager = MotionManager()
    @State private var elapsedTime: TimeInterval = 0
    @State private var timer: Timer?

    // Live UI controls
    @State private var showGyro: Bool = true
    @State private var serverOK: Bool? = nil
    @State private var serverStatusText: String = "Checking…"

    private var apiClient: APIClient? {
        guard !settings.apiBaseURL.isEmpty, !settings.apiToken.isEmpty else { return nil }
        return APIClient(baseURL: settings.apiBaseURL, token: settings.apiToken)
    }

    private var elapsedFormatted: String {
        let mins = Int(elapsedTime) / 60
        let secs = Int(elapsedTime) % 60
        return String(format: "%02d:%02d", mins, secs)
    }

    private var lastSample: SensorSample? {
        recordingStore.samples.last
    }

    private var isMotionFresh: Bool {
        // If we got a sample recently, show green dot.
        guard let last = lastSample else { return false }
        let nowMs = Int64(Date().timeIntervalSince1970 * 1000)
        return (nowMs - last.ts_ms) < 500 // within last 0.5s
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
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

                    // Connectivity status
                    GroupBox(label: Label("Connectivity", systemImage: "antenna.radiowaves.left.and.right")) {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text("Network")
                                Spacer()
                                Text(networkMonitor.isOnline ? networkMonitor.interfaceDescription : "Offline")
                                    .foregroundStyle(networkMonitor.isOnline ? .green : .red)
                            }

                            HStack {
                                Text("Server /health")
                                Spacer()
                                if let ok = serverOK {
                                    Text(ok ? "OK" : "Down")
                                        .foregroundStyle(ok ? .green : .red)
                                } else {
                                    Text(serverStatusText)
                                        .foregroundStyle(.secondary)
                                }
                            }

                            if !networkMonitor.isOnline {
                                Text("You appear to be offline. Upload/compute will fail until network returns.")
                                    .font(.caption)
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
                                .font(.system(size: 44, weight: .bold, design: .monospaced))
                            Text("Elapsed")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        VStack {
                            Text("\(recordingStore.samples.count)")
                                .font(.system(size: 44, weight: .bold, design: .monospaced))
                            Text("Samples")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.top, 4)

                    // Motion indicator + toggles
                    GroupBox(label: Label("Live", systemImage: "waveform")) {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack(spacing: 10) {
                                Circle()
                                    .fill(isMotionFresh ? Color.green : Color.gray)
                                    .frame(width: 10, height: 10)
                                Text(isMotionFresh ? "Motion detected" : "No fresh motion samples")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)

                                Spacer()

                                Toggle("Show Gyro", isOn: $showGyro)
                                    .labelsHidden()
                            }

                            // Live numeric readouts
                            if let s = lastSample {
                                VStack(alignment: .leading, spacing: 6) {
                                    Text("Acceleration (userAcceleration)")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)

                                    Text(String(format: "ax %.3f   ay %.3f   az %.3f", s.ax, s.ay, s.az))
                                        .font(.system(.body, design: .monospaced))

                                    if showGyro {
                                        Text("Gyro (rotationRate)")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                            .padding(.top, 6)

                                        Text(String(format: "gx %.3f   gy %.3f   gz %.3f", s.gx, s.gy, s.gz))
                                            .font(.system(.body, design: .monospaced))
                                    }
                                }
                            } else {
                                Text("No samples yet.")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .padding(.horizontal)

                    // Live graph (last ~10 seconds at 50Hz = 500 samples)
                    let windowSize = 500
                    let recent = recordingStore.samples.suffix(windowSize)

                    let accelMag: [Double] = recent.map { s in
                        let x = s.ax, y = s.ay, z = s.az
                        return (x * x + y * y + z * z).squareRoot()
                    }

                    let gyroMag: [Double] = recent.map { s in
                        let x = s.gx, y = s.gy, z = s.gz
                        return (x * x + y * y + z * z).squareRoot()
                    }

                    GroupBox(label: Label("Live Graph", systemImage: "chart.xyaxis.line")) {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Magnitude (last ~10s)")
                                .font(.caption)
                                .foregroundStyle(.secondary)

                            LiveLineChart(
                                values: accelMag,
                                color: .green,
                                minY: 0,
                                maxY: 2.0
                            )

                            if showGyro {
                                LiveLineChart(
                                    values: gyroMag,
                                    color: .blue,
                                    minY: 0,
                                    maxY: 10.0
                                )
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .padding(.horizontal)

                    // Record button
                    Button {
                        if recordingStore.isRecording {
                            stopRecordingAndAutoProcess()
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
                        .frame(maxWidth: .infinity)
                        .background(recordingStore.isRecording ? Color.red : Color.green,
                                    in: RoundedRectangle(cornerRadius: 16))
                        .padding(.horizontal)
                    }
                    .disabled(recordingStore.sessionId == nil || recordingStore.isAutoProcessing)

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

                    // Auto-processing status
                    if recordingStore.isAutoProcessing || !recordingStore.autoProcessingMessage.isEmpty || recordingStore.autoProcessingError != nil {
                        GroupBox(label: Label("Auto Upload + Compute", systemImage: "gearshape.2")) {
                            VStack(alignment: .leading, spacing: 8) {
                                if recordingStore.isAutoProcessing {
                                    HStack(spacing: 10) {
                                        ProgressView()
                                        Text(recordingStore.autoProcessingMessage)
                                    }
                                } else {
                                    Text(recordingStore.autoProcessingMessage)
                                        .foregroundStyle(recordingStore.autoProcessingError == nil ? .green : .secondary)
                                }

                                if let err = recordingStore.autoProcessingError {
                                    Text(err)
                                        .foregroundStyle(.red)
                                        .font(.caption)
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .padding(.horizontal)
                    }

                    Spacer(minLength: 20)
                }
                .padding(.top)
            }
            .navigationTitle("Recording")
            .task {
                await refreshHealth()
            }
        }
    }

    private func refreshHealth() async {
        guard networkMonitor.isOnline else {
            serverOK = false
            serverStatusText = "Offline"
            return
        }
        guard let client = apiClient else {
            serverOK = nil
            serverStatusText = "Configure API"
            return
        }
        do {
            serverStatusText = "Checking…"
            let ok = try await client.health()
            serverOK = ok
        } catch {
            serverOK = false
        }
    }

    private func startRecording() {
        guard let sessionId = recordingStore.sessionId,
              let horseName = recordingStore.sessionHorseName else { return }

        // Keep screen awake while recording
        UIApplication.shared.isIdleTimerDisabled = true

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

    private func stopRecordingAndAutoProcess() {
        motionManager.stop()
        recordingStore.stopRecording()
        timer?.invalidate()
        timer = nil

        // Re-enable screen sleep
        UIApplication.shared.isIdleTimerDisabled = false

        guard let client = apiClient else {
            recordingStore.autoProcessingError = "Configure API settings first."
            recordingStore.autoProcessingMessage = "Auto-processing skipped."
            return
        }

        // Kick off auto upload + compute
        Task {
            await recordingStore.uploadAndCompute(client: client)
        }
    }
}

#Preview {
    RecordingView()
        .environmentObject(AppSettings())
        .environmentObject(RecordingStore())
}
