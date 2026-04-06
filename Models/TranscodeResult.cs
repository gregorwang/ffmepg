namespace AnimeTranscoder.Models;

public sealed class TranscodeResult
{
    public bool Success { get; init; }
    public string ErrorMessage { get; init; } = string.Empty;
}
