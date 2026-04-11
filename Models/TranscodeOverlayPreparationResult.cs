namespace AnimeTranscoder.Models;

public sealed class TranscodeOverlayPreparationResult
{
    public bool Success { get; init; }
    public int? SubtitleStreamOrdinal { get; init; }
    public string DanmakuAssPath { get; init; } = string.Empty;
    public string DanmakuXmlPath { get; init; } = string.Empty;
    public int DanmakuXmlCommentCount { get; init; }
    public int DanmakuKeptCommentCount { get; init; }
    public string SubtitleAnalysisSource { get; init; } = string.Empty;
    public string SubtitleKindSummary { get; init; } = string.Empty;
    public string DanmakuSourceSummary { get; init; } = string.Empty;
    public string DanmakuPreparationSummary { get; init; } = string.Empty;
    public string ErrorMessage { get; init; } = string.Empty;

    public static TranscodeOverlayPreparationResult Fail(string errorMessage)
    {
        return new TranscodeOverlayPreparationResult
        {
            Success = false,
            ErrorMessage = errorMessage
        };
    }

    public static TranscodeOverlayPreparationResult SuccessState(
        int? subtitleStreamOrdinal,
        string danmakuAssPath,
        string danmakuXmlPath,
        int danmakuXmlCommentCount,
        int danmakuKeptCommentCount,
        string subtitleAnalysisSource,
        string subtitleKindSummary,
        string danmakuSourceSummary,
        string danmakuPreparationSummary)
    {
        return new TranscodeOverlayPreparationResult
        {
            Success = true,
            SubtitleStreamOrdinal = subtitleStreamOrdinal,
            DanmakuAssPath = danmakuAssPath,
            DanmakuXmlPath = danmakuXmlPath,
            DanmakuXmlCommentCount = danmakuXmlCommentCount,
            DanmakuKeptCommentCount = danmakuKeptCommentCount,
            SubtitleAnalysisSource = subtitleAnalysisSource,
            SubtitleKindSummary = subtitleKindSummary,
            DanmakuSourceSummary = danmakuSourceSummary,
            DanmakuPreparationSummary = danmakuPreparationSummary
        };
    }
}
