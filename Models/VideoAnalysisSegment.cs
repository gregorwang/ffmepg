namespace AnimeTranscoder.Models;

public sealed class VideoAnalysisSegment
{
    public double StartSeconds { get; init; }
    public double EndSeconds { get; init; }
    public double DurationSeconds { get; init; }
    public string Kind { get; init; } = string.Empty;

    public string StartLabel => $"{StartSeconds:0.000}s";
    public string EndLabel => $"{EndSeconds:0.000}s";
    public string DurationLabel => $"{DurationSeconds:0.000}s";
    public string Summary => $"{Kind} | {StartLabel} - {EndLabel} | 持续 {DurationLabel}";
}
