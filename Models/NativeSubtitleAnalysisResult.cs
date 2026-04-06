namespace AnimeTranscoder.Models;

public sealed class NativeSubtitleAnalysisResult
{
    public bool IsAvailable { get; init; }
    public bool IsFallback { get; init; }
    public string Source { get; init; } = "fallback";
    public string Message { get; init; } = string.Empty;
    public IReadOnlyList<SubtitleTrackInfo> SubtitleTracks { get; init; } = [];
}
