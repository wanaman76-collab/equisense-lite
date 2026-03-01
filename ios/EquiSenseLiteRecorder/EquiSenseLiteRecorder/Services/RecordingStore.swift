import Foundation
import Combine

class RecordingStore: ObservableObject {
    @Published var samples: [SensorSample] = []
    @Published var isRecording: Bool = false
    @Published var recordingStartTime: Date?
    @Published var sessionId: Int?
    @Published var sessionHorseName: String?
    @Published var isUploaded: Bool = false

    private var fileURL: URL? {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first
        return docs?.appendingPathComponent("recording_\(sessionId ?? 0).jsonl")
    }

    func startRecording(sessionId: Int, horseName: String) {
        self.sessionId = sessionId
        self.sessionHorseName = horseName
        self.samples = []
        self.isRecording = true
        self.recordingStartTime = Date()
        self.isUploaded = false
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
    }
}
