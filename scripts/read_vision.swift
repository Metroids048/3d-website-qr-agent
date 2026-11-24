import Foundation
import Vision

// Adapted from the project's native Vision regression reader.
let request = VNDetectBarcodesRequest()
request.symbologies = [.qr]
do {
    try VNImageRequestHandler(url: URL(fileURLWithPath: CommandLine.arguments[1])).perform([request])
    let observations = request.results ?? []
    let payloads = observations.compactMap(\.payloadStringValue)
    let result = try JSONEncoder().encode(payloads)
    print(String(decoding: result, as: UTF8.self))
} catch {
    FileHandle.standardError.write(Data("\(error)\n".utf8))
    exit(1)
}
