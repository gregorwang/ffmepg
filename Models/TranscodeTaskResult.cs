namespace AnimeTranscoder.Models;

public sealed class TranscodeTaskResult
{
    public Guid TaskId { get; init; }
    public string InputPath { get; init; } = string.Empty;
    public string OutputPath { get; set; } = string.Empty;
    public JobStatus Status { get; set; } = JobStatus.Pending;
    public double ProgressPercent { get; set; }
    public string Speed { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
    public string EncoderUsed { get; set; } = string.Empty;
    public double SourceDurationSeconds { get; set; }
    public int? SubtitleStreamOrdinal { get; set; }
    public string SubtitleAnalysisSource { get; set; } = string.Empty;
    public string SubtitleKindSummary { get; set; } = string.Empty;
    public string DanmakuSourceSummary { get; set; } = string.Empty;
    public string DanmakuPreparationSummary { get; set; } = string.Empty;
    public string DanmakuXmlPath { get; set; } = string.Empty;
    public string DanmakuAssPath { get; set; } = string.Empty;
    public int DanmakuXmlCommentCount { get; set; }
    public int DanmakuKeptCommentCount { get; set; }
    public bool SourceDeleted { get; set; }

    public string FileName => Path.GetFileName(InputPath);
}
