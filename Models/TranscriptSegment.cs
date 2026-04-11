namespace AnimeTranscoder.Models;

public sealed class TranscriptSegment
{
    public string Id { get; init; } = string.Empty;
    public double Start { get; init; }
    public double End { get; init; }
    public string Text { get; init; } = string.Empty;
    public string Language { get; init; } = string.Empty;
    public string? Speaker { get; init; }
    public double? Confidence { get; init; }
    public string Source { get; init; } = string.Empty;
    public bool Overlap { get; init; }
    public string Channel { get; init; } = "mono";

    public double Duration => Math.Max(End - Start, 0d);
}
