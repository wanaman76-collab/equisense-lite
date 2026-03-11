import SwiftUI

struct UploadView: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var recordingStore: RecordingStore

    private let uploadBatchSize = 200

    @State private var isUploading = false
    @State private var uploadedCount = 0
    @State private var totalCount = 0
    @State private var statusMessage = ""
    @State private var isError = false
    @State private var isComputing = false

    @State private var computeResult: ComputeResponse?

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

                if let result = computeResult {
                    Section(header: Text("Report")) {
                        HStack {
                            Text("Overall")
                            Spacer()
                            Text(result.report.overall_label)
                                .bold()
                                .foregroundStyle(colorForOverall(result.report.overall_label))
                        }
                        HStack {
                            Text("Trot confidence")
                            Spacer()
                            Text(result.report.trot_confidence)
                                .foregroundStyle(.secondary)
                        }
                        HStack {
                            Text("Windows")
                            Spacer()
                            Text("\(result.windows)")
                        }
                        HStack {
                            Text("Anomalies")
                            Spacer()
                            Text("\(result.anomalies_total) (med/high: \(result.anomalies_medium_high))")
                        }
                    }

                    Section(header: Text("Notes")) {
                        if result.report.explanations.isEmpty {
                            Text("—").foregroundStyle(.secondary)
                        } else {
                            ForEach(result.report.explanations, id: \.self) { line in
                                Text("• \(line)")
                            }
                        }
                    }

                    Section(header: Text("Metrics")) {
                        metricRow("Cadence mean", result.report.metrics.cadence_spm_mean, digits: 1, suffix: " spm")
                        metricRow("Cadence std", result.report.metrics.cadence_spm_std, digits: 1, suffix: " spm")
                        metricRow("Stride var median", result.report.metrics.stride_var_median, digits: 4, suffix: "")
                        metricRow("Asymmetry median", result.report.metrics.asymmetry_proxy_median, digits: 4, suffix: "")
                        metricRow("Energy mean", result.report.metrics.energy_mean, digits: 4, suffix: "")
                        HStack {
                            Text("Windows with gaps")
                            Spacer()
                            Text("\(result.report.metrics.windows_with_gaps)")
                        }
                    }

                    Section(header: Text("Baseline Used")) {
                        baselineRow("cadence_spm", result.report.baseline.cadence_spm_median, result.report.baseline.cadence_spm_mad, digitsMedian: 1, digitsMad: 3)
                        baselineRow("stride_var", result.report.baseline.stride_var_median, result.report.baseline.stride_var_mad, digitsMedian: 4, digitsMad: 4)
                        baselineRow("asymmetry_proxy", result.report.baseline.asymmetry_proxy_median, result.report.baseline.asymmetry_proxy_mad, digitsMedian: 4, digitsMad: 4)
                    }
                }

                Section(header: Text("Data Management")) {
                    Button(role: .destructive) {
                        recordingStore.clearData()
                        statusMessage = "Data cleared."
                        isError = false
                        uploadedCount = 0
                        totalCount = 0
                        computeResult = nil
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

    private func metricRow(_ label: String, _ value: Double?, digits: Int, suffix: String) -> some View {
        HStack {
            Text(label)
            Spacer()
            if let value {
                Text("\(value, specifier: "%.\(digits)f")\(suffix)")
            } else {
                Text("—").foregroundStyle(.secondary)
            }
        }
    }

    private func baselineRow(_ feature: String, _ median: Double?, _ mad: Double?, digitsMedian: Int, digitsMad: Int) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(feature).bold()
            HStack {
                Text("median")
                Spacer()
                Text(median != nil ? "\(median!, specifier: "%.\(digitsMedian)f")" : "—")
                    .foregroundStyle(.secondary)
            }
            HStack {
                Text("MAD")
                Spacer()
                Text(mad != nil ? "\(mad!, specifier: "%.\(digitsMad)f")" : "—")
                    .foregroundStyle(.secondary)
            }
        }
    }

    private func colorForOverall(_ label: String) -> Color {
        switch label.uppercased() {
        case "NORMAL": return .green
        case "WATCH": return .orange
        default: return .red
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
        computeResult = nil

        do {
            let stored = try await client.uploadAll(
                sessionId: sessionId,
                samples: samples,
                batchSize: uploadBatchSize
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
            computeResult = result
            statusMessage = "Analysis complete ✓ (\(result.report.overall_label))"
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
