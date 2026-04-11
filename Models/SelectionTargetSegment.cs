namespace AnimeTranscoder.Models;

public sealed class SelectionTargetSegment
{
    public string SegmentId { get; init; } = string.Empty;
    public SelectionAction Action { get; init; }
    public string Reason { get; init; } = string.Empty;
}
