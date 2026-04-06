namespace AnimeTranscoder.Models;

public sealed class OutputValidationResult
{
    public bool IsMatch { get; init; }
    public bool IsFallback { get; init; }
    public string Source { get; init; } = "unknown";
    public string Message { get; init; } = string.Empty;
    public bool OutputReadable { get; init; }
    public string OutputAudioCodec { get; init; } = string.Empty;
    public int OutputAudioChannels { get; init; }
    public string OutputAudioChannelLayout { get; init; } = string.Empty;
    public double InputDurationSeconds { get; init; }
    public double OutputDurationSeconds { get; init; }
    public double DifferenceSeconds { get; init; }
}
