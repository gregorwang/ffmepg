namespace AnimeTranscoder.Models;

public sealed class HardwareInfo
{
    public bool IsNvencAvailable { get; init; }
    public string FfmpegPath { get; init; } = string.Empty;
    public string FfprobePath { get; init; } = string.Empty;
}
