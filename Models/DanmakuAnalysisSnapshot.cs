namespace AnimeTranscoder.Models;

public sealed class DanmakuAnalysisSnapshot
{
    public string XmlPath { get; init; } = string.Empty;
    public int XmlCommentCount { get; init; }
    public int KeptCommentCount { get; init; }
    public IReadOnlyList<DanmakuComment> Comments { get; init; } = [];
}
