import SwiftUI

struct UploadView: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var recordingStore: RecordingStore

    @State private var isUploading = false
    @State private var uploadedCount = 0
    @State private var totalCount = 0
    @State private var statusMessage = ""
    @State private var isError = false
    @State private var isComputing = false

    private var apiClient: APIClient? {
        guard !settings.apiBaseURL.isEmpty, !settings.apiToken.isEmpty else { return nil }
        return APIClient(baseURL: settings.apiBaseURL, token: settings.apiToken)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section(header: Text("Recording Data")) {
                    LabeledContent("Samples", value: "\(recordingStore.samples.count)")
                    if let horse = recordingStore.sessionHorseName {
                        LabeledContent("Horse", value: horse)
                    }
                    if let sid = recordingStore.sessionId {
                        LabeledContent("Session ID", value: String(sid))
                    }
                    LabeledContent("Uploaded", value: recordingStore.isUploaded ? "Yes ✓" : "No")
                }

                Section(header: Text("Upload")) {
                    if isUploading {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Uploading \(uploadedCount) / \(totalCount) samples…")
                                .font(.caption)
                            ProgressView(value: totalCount > 0 ? Double(uploadedCount) / Double(totalCount) : 0)
                        }
                    } else {
                        Button {
                            Task { await uploadData() }
                        } label: {
                            Label("Upload to Server", systemImage: "icloud.and.arrow.up")
                        }
                        .disabled(recordingStore.samples.isEmpty || apiClient == nil ||
                                  recordingStore.sessionId == nil || recordingStore.isRecording)
                    }
                }

                Section(header: Text("Analysis")) {
                    Button {
                        Task { await computeAnalysis() }
                    } label: {
                        if isComputing {
                            HStack {
                                ProgressView()
                                Text("Computing…").padding(.leading, 8)
                            }
                        } else {
                            Label("Compute Analysis", systemImage: "chart.bar.xaxis")
                        }
                    }
                    .disabled(!recordingStore.isUploaded || recordingStore.sessionId == nil ||
                              apiClient == nil || isComputing)
                }

                Section(header: Text("Data Management")) {
                    Button(role: .destructive) {
                        recordingStore.clearData()
                        statusMessage = "Data cleared."
                        isError = false
                        uploadedCount = 0
                        totalCount = 0
                    } label: {
                        Label("Clear Uploaded Data", systemImage: "trash")
                    }
                    .disabled(recordingStore.samples.isEmpty)
                }

                if !statusMessage.isEmpty {
                    Section {
                        Text(statusMessage)
                            .foregroundStyle(isError ? .red : .green)
                    }
                }
            }
            .navigationTitle("Upload")
        }
    }

    private func uploadData() async {
        guard let client = apiClient,
              let sessionId = recordingStore.sessionId else { return }
        let samples = recordingStore.samples
        guard !samples.isEmpty else { return }

        isUploading = true
        totalCount = samples.count
        uploadedCount = 0
        statusMessage = ""

        do {
            let stored = try await client.uploadAll(
                sessionId: sessionId,
                samples: samples,
                batchSize: 200
            ) { sent, _ in
                Task { @MainActor in
                    uploadedCount = sent
                }
            }
            recordingStore.markUploaded()
            statusMessage = "Uploaded \(stored) samples successfully ✓"
            isError = false
        } catch {
            statusMessage = "Upload failed: \(error.localizedDescription)"
            isError = true
        }
        isUploading = false
    }

    private func computeAnalysis() async {
        guard let client = apiClient,
              let sessionId = recordingStore.sessionId else { return }
        isComputing = true
        defer { isComputing = false }
        do {
            let result = try await client.compute(sessionId: sessionId)
            statusMessage = "Analysis complete: \(result.windows) windows processed ✓"
            isError = false
        } catch {
            statusMessage = "Compute failed: \(error.localizedDescription)"
            isError = true
        }
    }
}

#Preview {
    UploadView()
        .environmentObject(AppSettings())
        .environmentObject(RecordingStore())
}
