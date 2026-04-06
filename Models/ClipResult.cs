namespace AnimeTranscoder.Models;

public sealed class ClipResult
{
    public bool Success { get; init; }
    public string OutputPath { get; init; } = string.Empty;
    public string? ErrorMessage { get; init; }
}
