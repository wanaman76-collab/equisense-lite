import SwiftUI

struct HorseSessionView: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var recordingStore: RecordingStore

    @State private var horseName = ""
    @State private var surface = ""
    @State private var horses: [HorseOut] = []
    @State private var selectedHorse: HorseOut?
    @State private var statusMessage = ""
    @State private var isError = false
    @State private var isLoading = false

    private var apiClient: APIClient? {
        guard !settings.apiBaseURL.isEmpty, !settings.apiToken.isEmpty else { return nil }
        return APIClient(baseURL: settings.apiBaseURL, token: settings.apiToken)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section(header: Text("Create Horse")) {
                    TextField("Horse name", text: $horseName)
                        .autocorrectionDisabled()
                    Button("Create Horse") {
                        Task { await createHorse() }
                    }
                    .disabled(horseName.trimmingCharacters(in: .whitespaces).isEmpty || apiClient == nil || isLoading)
                }

                Section(header: Text("Select Horse")) {
                    if horses.isEmpty {
                        Text("No horses found. Create one above or refresh.")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(horses) { horse in
                            Button {
                                selectedHorse = horse
                                statusMessage = "Selected: \(horse.name)"
                                isError = false
                            } label: {
                                HStack {
                                    VStack(alignment: .leading) {
                                        Text(horse.name).bold()
                                        if let notes = horse.notes, !notes.isEmpty {
                                            Text(notes).font(.caption).foregroundStyle(.secondary)
                                        }
                                    }
                                    Spacer()
                                    if selectedHorse?.id == horse.id {
                                        Image(systemName: "checkmark.circle.fill")
                                            .foregroundStyle(.green)
                                    }
                                }
                            }
                            .foregroundStyle(.primary)
                        }
                    }
                }

                if let horse = selectedHorse {
                    Section(header: Text("Start Session for \(horse.name)")) {
                        TextField("Surface (optional, e.g. grass, arena)", text: $surface)
                            .autocorrectionDisabled()
                        Button("Start Session") {
                            Task { await startSession(horse: horse) }
                        }
                        .disabled(apiClient == nil || isLoading)
                    }
                }

                if let sessionId = recordingStore.sessionId,
                   let horseName = recordingStore.sessionHorseName {
                    Section(header: Text("Current Session")) {
                        LabeledContent("Horse", value: horseName)
                        LabeledContent("Session ID", value: String(sessionId))
                    }
                }

                if !statusMessage.isEmpty {
                    Section {
                        Text(statusMessage)
                            .foregroundStyle(isError ? .red : .green)
                    }
                }
            }
            .navigationTitle("Horse & Session")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        Task { await loadHorses() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .disabled(isLoading)
                }
            }
            .task { await loadHorses() }
            .overlay {
                if isLoading {
                    ProgressView()
                        .padding()
                        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
                }
            }
        }
    }

    private func loadHorses() async {
        guard let client = apiClient else {
            statusMessage = "Configure API settings first."
            isError = true
            return
        }
        isLoading = true
        defer { isLoading = false }
        do {
            horses = try await client.listHorses()
            if !statusMessage.contains("Session") {
                statusMessage = ""
            }
        } catch {
            statusMessage = "Failed to load horses: \(error.localizedDescription)"
            isError = true
        }
    }

    private func createHorse() async {
        guard let client = apiClient else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            let horse = try await client.createHorse(name: horseName.trimmingCharacters(in: .whitespaces), notes: nil)
            horses.append(horse)
            selectedHorse = horse
            statusMessage = "Horse '\(horse.name)' created!"
            isError = false
            horseName = ""
        } catch {
            statusMessage = "Error: \(error.localizedDescription)"
            isError = true
        }
    }

    private func startSession(horse: HorseOut) async {
        guard let client = apiClient else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            let surfaceVal = surface.trimmingCharacters(in: .whitespaces)
            let session = try await client.startSession(
                horseId: horse.id,
                surface: surfaceVal.isEmpty ? nil : surfaceVal,
                notes: nil
            )
            recordingStore.sessionId = session.id
            recordingStore.sessionHorseName = horse.name
            statusMessage = "Session \(session.id) started for \(horse.name) ✓"
            isError = false
        } catch {
            statusMessage = "Error: \(error.localizedDescription)"
            isError = true
        }
    }
}

#Preview {
    HorseSessionView()
        .environmentObject(AppSettings())
        .environmentObject(RecordingStore())
}
