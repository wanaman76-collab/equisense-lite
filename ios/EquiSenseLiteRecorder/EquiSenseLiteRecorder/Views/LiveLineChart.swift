import SwiftUI

struct LiveLineChart: View {
    let values: [Double]
    let color: Color
    let minY: Double
    let maxY: Double
    var showBackground: Bool = true

    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            let h = geo.size.height
            let count = values.count

            ZStack {
                if showBackground {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color(.secondarySystemBackground))
                }

                // Midline (for visual reference)
                Path { p in
                    p.move(to: CGPoint(x: 0, y: h / 2))
                    p.addLine(to: CGPoint(x: w, y: h / 2))
                }
                .stroke(Color.primary.opacity(0.08), lineWidth: 1)

                Path { path in
                    guard count > 1 else { return }

                    func x(_ i: Int) -> CGFloat {
                        w * CGFloat(i) / CGFloat(max(count - 1, 1))
                    }

                    func y(_ v: Double) -> CGFloat {
                        let clamped = min(max(v, minY), maxY)
                        let denom = (maxY - minY == 0) ? 1 : (maxY - minY)
                        let t = (clamped - minY) / denom
                        return h * (1 - CGFloat(t))
                    }

                    path.move(to: CGPoint(x: x(0), y: y(values[0])))
                    for i in 1..<count {
                        path.addLine(to: CGPoint(x: x(i), y: y(values[i])))
                    }
                }
                .stroke(color, style: StrokeStyle(lineWidth: 2, lineJoin: .round, lineCap: .round))
                .padding(10)
            }
        }
        .frame(height: 140)
    }
}
