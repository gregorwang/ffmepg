namespace AnimeTranscoder.Models;

public sealed class BatchFrameSampleResult
{
    public bool Success { get; init; }
    public bool IsFallback { get; init; }
    public string Source { get; init; } = "unknown";
    public string Message { get; init; } = string.Empty;
    public string OutputDirectory { get; init; } = string.Empty;
    public IReadOnlyList<DiagnosticFrameSample> Samples { get; init; } = [];
}
