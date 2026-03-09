import SwiftUI
import Charts

struct LiveLineChart: View {
    var data: [Double]

    var body: some View {
        VStack {
            Text("Acceleration Magnitude")
                .font(.headline)
            LineChart(data: data)
                .frame(height: 300)
        }
    }
}

struct LineChart: View {
    var data: [Double]

    var body: some View {
        Line(viewData: data)
    }
    
    struct Line: View {
        var viewData: [Double]

        var body: some View {
            // Implementation of the line drawing
            // SwiftUI drawing code goes here
            Path { path in
                let step = 300 / viewData.count
                for index in viewData.indices {
                    let x = Double(index) * Double(step)
                    let y = 300 - (viewData[index] * 300)
                    if index == 0 {
                        path.move(to: CGPoint(x: x, y: y))
                    } else {
                        path.addLine(to: CGPoint(x: x, y: y))
                    }
                }
            }
            .stroke(Color.blue, lineWidth: 2)
        }
    }
}