import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var settings: AppSettings

    var body: some View {
        NavigationStack {
            Form {
                Section(header: Text("API Configuration")) {
                    TextField("Base URL (e.g. https://api.example.com)", text: $settings.apiBaseURL)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)

                    SecureField("API Token (X-API-Token)", text: $settings.apiToken)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                }

                Section(header: Text("Status")) {
                    HStack {
                        Text("Base URL")
                        Spacer()
                        Text(settings.apiBaseURL.isEmpty ? "Not set" : "✓ Set")
                            .foregroundStyle(settings.apiBaseURL.isEmpty ? .red : .green)
                    }
                    HStack {
                        Text("Token")
                        Spacer()
                        Text(settings.apiToken.isEmpty ? "Not set" : "✓ Set")
                            .foregroundStyle(settings.apiToken.isEmpty ? .red : .green)
                    }
                }
            }
            .navigationTitle("Settings")
        }
    }
}

#Preview {
    SettingsView()
        .environmentObject(AppSettings())
}
