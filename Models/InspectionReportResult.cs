namespace AnimeTranscoder.Models;

public sealed class InspectionReportResult
{
    public DateTime GeneratedAt { get; init; } = DateTime.Now;
    public string InputPath { get; init; } = string.Empty;
    public string OutputDirectory { get; init; } = string.Empty;
    public string Source { get; init; } = string.Empty;
    public int TotalSamples { get; init; }
    public int AttentionSamples { get; init; }
    public string Summary { get; init; } = string.Empty;
    public IReadOnlyList<DiagnosticFrameSample> Samples { get; init; } = [];
}
