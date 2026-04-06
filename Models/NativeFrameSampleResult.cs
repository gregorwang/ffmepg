namespace AnimeTranscoder.Models;

public sealed class NativeFrameSampleResult
{
    public bool Success { get; init; }
    public bool IsFallback { get; init; }
    public string Source { get; init; } = "unknown";
    public string Message { get; init; } = string.Empty;
    public string InputPath { get; init; } = string.Empty;
    public string OutputPath { get; init; } = string.Empty;
    public double TimeSeconds { get; init; }
}
