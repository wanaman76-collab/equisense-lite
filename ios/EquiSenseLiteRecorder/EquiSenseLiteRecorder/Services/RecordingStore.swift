import Foundation
import Combine

@MainActor
class RecordingStore: ObservableObject {
    @Published var samples: [SensorSample] = []
    @Published var isRecording: Bool = false
    @Published var recordingStartTime: Date?
    @Published var sessionId: Int?
    @Published var sessionHorseName: String?
    @Published var sessionHorseId: Int?
    @Published var isUploaded: Bool = false

    // Latest compute report (used by Recording/Upload screens)
    @Published var lastComputeResult: ComputeResponse? = nil

    // Upload/compute status (so Recording tab can show progress)
    @Published var isAutoProcessing: Bool = false
    @Published var autoProcessingMessage: String = ""
    @Published var autoProcessingError: String? = nil

    // MARK: - Live publisher

    private var livePublisher: LivePublisher?
    private let networkMonitor: NetworkMonitor

    init(networkMonitor: NetworkMonitor = NetworkMonitor()) {
        self.networkMonitor = networkMonitor
    }

    private var fileURL: URL? {
        guard let sid = sessionId else { return nil }
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first
        return docs?.appendingPathComponent("recording_\(sid).jsonl")
    }

    func startRecording(sessionId: Int, horseId: Int, horseName: String, client: APIClient? = nil) {
        self.sessionId = sessionId
        self.sessionHorseId = horseId
        self.sessionHorseName = horseName
        self.samples = []
        self.isRecording = true
        self.recordingStartTime = Date()
        self.isUploaded = false

        self.lastComputeResult = nil

        self.isAutoProcessing = false
        self.autoProcessingMessage = ""
        self.autoProcessingError = nil

        // Start live publisher if a client is available
        if let client {
            let publisher = LivePublisher(networkMonitor: networkMonitor)
            publisher.start(sessionId: sessionId, client: client)
            livePublisher = publisher
        }
    }

    func addSample(_ sample: SensorSample) {
        samples.append(sample)
        livePublisher?.enqueue(sample)
    }

    func stopRecording() {
        isRecording = false
        livePublisher?.stop()
        livePublisher = nil
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
        livePublisher?.stop()
        livePublisher = nil
        if let url = fileURL {
            try? FileManager.default.removeItem(at: url)
        }
        samples = []
        isUploaded = false
        sessionId = nil
        sessionHorseName = nil
        sessionHorseId = nil
        recordingStartTime = nil

        lastComputeResult = nil

        isAutoProcessing = false
        autoProcessingMessage = ""
        autoProcessingError = nil
    }

    /// Upload-only mode (compute intentionally skipped to avoid OOM/502).
    func uploadOnly(client: APIClient) async {
        guard let sid = sessionId else { return }
        let samplesSnapshot = self.samples
        guard !samplesSnapshot.isEmpty else {
            autoProcessingError = "No samples to upload."
            return
        }

        isAutoProcessing = true
        autoProcessingError = nil
        autoProcessingMessage = "Uploading…"
        lastComputeResult = nil

        do {
            _ = try await client.uploadAll(sessionId: sid, samples: samplesSnapshot, batchSize: 200) { sent, total in
                self.autoProcessingMessage = "Uploading \(sent) / \(total)…"
            }
            self.isUploaded = true
            self.autoProcessingMessage = "Upload complete. Compute skipped."
        } catch {
            self.autoProcessingError = error.localizedDescription
            self.autoProcessingMessage = "Upload failed."
        }

        isAutoProcessing = false
    }

    /// Keep old method if you want to re-enable later.
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
        lastComputeResult = nil

        do {
            _ = try await client.uploadAll(sessionId: sid, samples: samplesSnapshot, batchSize: 200) { sent, total in
                self.autoProcessingMessage = "Uploading \(sent) / \(total)…"
            }
            self.isUploaded = true
            self.autoProcessingMessage = "Upload complete. Computing…"

            let result = try await client.compute(sessionId: sid)
            self.lastComputeResult = result
            self.autoProcessingMessage = "Compute complete ✓ (\(result.report.overall_label))"
        } catch {
            self.autoProcessingError = error.localizedDescription
            self.autoProcessingMessage = "Auto-processing failed."
        }

        isAutoProcessing = false
    }
}
