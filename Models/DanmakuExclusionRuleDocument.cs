namespace AnimeTranscoder.Models;

public sealed class DanmakuExclusionRuleDocument
{
    public string InputPath { get; init; } = string.Empty;
    public string XmlPath { get; init; } = string.Empty;
    public string AssPath { get; init; } = string.Empty;
    public DateTime ExportedAt { get; init; }
    public List<string> ExcludedCommentKeys { get; init; } = [];
}
