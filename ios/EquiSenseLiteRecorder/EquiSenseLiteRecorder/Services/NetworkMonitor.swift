import Foundation
import Network
import Combine

final class NetworkMonitor: ObservableObject {
    @Published private(set) var isOnline: Bool = true
    @Published private(set) var isExpensive: Bool = false
    @Published private(set) var interfaceDescription: String = "Unknown"

    private let monitor = NWPathMonitor()
    private let queue = DispatchQueue(label: "NetworkMonitor")

    init() {
        monitor.pathUpdateHandler = { [weak self] path in
            DispatchQueue.main.async {
                self?.isOnline = (path.status == .satisfied)
                self?.isExpensive = path.isExpensive

                if path.usesInterfaceType(.wifi) {
                    self?.interfaceDescription = "Wi‑Fi"
                } else if path.usesInterfaceType(.cellular) {
                    self?.interfaceDescription = "Cellular"
                } else if path.usesInterfaceType(.wiredEthernet) {
                    self?.interfaceDescription = "Ethernet"
                } else {
                    self?.interfaceDescription = self?.isOnline == true ? "Online" : "Offline"
                }
            }
        }
        monitor.start(queue: queue)
    }

    deinit {
        monitor.cancel()
    }
}
