namespace AnimeTranscoder.Models;

public sealed class DanmakuPreparationResult
{
    public bool Success { get; init; }
    public string FailedStage { get; init; } = string.Empty;
    public string ErrorMessage { get; init; } = string.Empty;
    public AnimeEpisodeMatch? EpisodeMatch { get; init; }
    public BangumiSeasonInfo? Season { get; init; }
    public BangumiEpisodeInfo? Episode { get; init; }
    public string XmlPath { get; init; } = string.Empty;
    public string AssPath { get; init; } = string.Empty;
    public int XmlCommentCount { get; init; }
    public int AssCommentCount { get; init; }
    public string Source { get; init; } = "bilibili-danmaku";
    public string KindSummary { get; init; } = string.Empty;
    public string Summary { get; init; } = string.Empty;
}
