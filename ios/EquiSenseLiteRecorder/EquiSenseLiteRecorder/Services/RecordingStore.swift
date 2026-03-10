import Foundation
import Combine

@MainActor
class RecordingStore: ObservableObject {
    @Published var samples: [SensorSample] = []
    @Published var isRecording: Bool = false
    @Published var recordingStartTime: Date?
    @Published var sessionId: Int?
    @Published var sessionHorseName: String?
    @Published var isUploaded: Bool = false

    // Upload/compute status (so Recording tab can show progress)
    @Published var isAutoProcessing: Bool = false
    @Published var autoProcessingMessage: String = ""
    @Published var autoProcessingError: String? = nil

    private var fileURL: URL? {
        guard let sid = sessionId else { return nil }
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first
        return docs?.appendingPathComponent("recording_\(sid).jsonl")
    }

    func startRecording(sessionId: Int, horseName: String) {
        self.sessionId = sessionId
        self.sessionHorseName = horseName
        self.samples = []
        self.isRecording = true
        self.recordingStartTime = Date()
        self.isUploaded = false

        self.isAutoProcessing = false
        self.autoProcessingMessage = ""
        self.autoProcessingError = nil
    }

    func addSample(_ sample: SensorSample) {
        samples.append(sample)
    }

    func stopRecording() {
        isRecording = false
        saveToFile()
    }

    private func saveToFile() {
        guard let url = fileURL else { return }
        let encoder = JSONEncoder()
        let lines = samples
            .compactMap { try? encoder.encode($0) }
            .compactMap { String(data: $0, encoding: .utf8) }
            .joined(separator: "\n")
        try? lines.write(to: url, atomically: true, encoding: .utf8)
    }

    func markUploaded() {
        isUploaded = true
    }

    func clearData() {
        if let url = fileURL {
            try? FileManager.default.removeItem(at: url)
        }
        samples = []
        isUploaded = false
        sessionId = nil
        sessionHorseName = nil
        recordingStartTime = nil

        isAutoProcessing = false
        autoProcessingMessage = ""
        autoProcessingError = nil
    }

    /// Upload then compute analysis (intended for auto-run after stopping recording).
    func uploadAndCompute(client: APIClient) async {
        guard let sid = sessionId else { return }
        let samplesSnapshot = self.samples
        guard !samplesSnapshot.isEmpty else {
            autoProcessingError = "No samples to upload."
            return
        }

        isAutoProcessing = true
        autoProcessingError = nil
        autoProcessingMessage = "Uploading…"

        do {
            _ = try await client.uploadAll(sessionId: sid, samples: samplesSnapshot, batchSize: 200) { sent, total in
                self.autoProcessingMessage = "Uploading \(sent) / \(total)…"
            }
            self.isUploaded = true
            self.autoProcessingMessage = "Upload complete. Computing…"

            _ = try await client.compute(sessionId: sid)
            self.autoProcessingMessage = "Compute complete ✓"
        } catch {
            self.autoProcessingError = error.localizedDescription
            self.autoProcessingMessage = "Auto-processing failed."
        }

        isAutoProcessing = false
    }
}
