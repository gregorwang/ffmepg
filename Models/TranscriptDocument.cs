namespace AnimeTranscoder.Models;

public sealed class TranscriptDocument
{
    public string Version { get; init; } = "1.0";
    public string MediaPath { get; init; } = string.Empty;
    public string AudioPath { get; init; } = string.Empty;
    public List<TranscriptSegment> Segments { get; init; } = [];
}
