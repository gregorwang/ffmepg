namespace AnimeTranscoder.Models;

public sealed class FramePreviewResult
{
    public bool Success { get; init; }
    public string OutputPath { get; init; } = string.Empty;
    public string Message { get; init; } = string.Empty;
}
