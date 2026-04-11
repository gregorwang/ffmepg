namespace AnimeTranscoder.Models;

public sealed class SelectionDocument
{
    public string Version { get; init; } = "1.0";
    public string TranscriptVersion { get; init; } = "1.0";
    public string DecisionSource { get; init; } = "external-agent";
    public string ConflictPolicy { get; init; } = "exclude_wins";
    public List<SelectionTargetSegment> TargetSegments { get; init; } = [];
}
