namespace AnimeTranscoder.Models;

public sealed class TaskHistoryEntry
{
    public Guid Id { get; init; } = Guid.NewGuid();
    public DateTime RecordedAt { get; init; } = DateTime.Now;
    public string InputPath { get; init; } = string.Empty;
    public string OutputPath { get; init; } = string.Empty;
    public string FileName { get; init; } = string.Empty;
    public JobStatus Status { get; init; }
    public string StatusText { get; init; } = string.Empty;
    public string Message { get; init; } = string.Empty;
    public string EncoderUsed { get; init; } = string.Empty;
    public int? SubtitleStreamOrdinal { get; init; }
    public string SubtitleAnalysisSource { get; init; } = string.Empty;
    public string SubtitleKindSummary { get; init; } = string.Empty;
}
