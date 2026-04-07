namespace AnimeTranscoder.Models;

public sealed class DanmakuComment
{
    public double TimeSeconds { get; init; }
    public int Mode { get; init; }
    public int FontSize { get; init; }
    public int Color { get; init; }
    public string Content { get; init; } = string.Empty;
}
