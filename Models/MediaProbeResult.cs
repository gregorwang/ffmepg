namespace AnimeTranscoder.Models;

public sealed class MediaProbeResult
{
    public string Path { get; init; } = string.Empty;
    public long FileSizeBytes { get; init; }
    public TimeSpan Duration { get; init; }
    public List<AudioTrackInfo> AudioTracks { get; init; } = [];
    public List<SubtitleTrackInfo> SubtitleTracks { get; init; } = [];
    public string AnalysisSource { get; init; } = "ffprobe";
    public string Message { get; init; } = string.Empty;
}
