namespace AnimeTranscoder.Models;

public sealed class WorkflowProgress
{
    public string Stage { get; init; } = string.Empty;
    public double ProgressPercent { get; init; }
    public string Speed { get; init; } = string.Empty;
    public string Message { get; init; } = string.Empty;
    public string ItemId { get; init; } = string.Empty;
    public string ItemPath { get; init; } = string.Empty;
    public DateTimeOffset Timestamp { get; init; } = DateTimeOffset.UtcNow;
}
