namespace AnimeTranscoder.Models;

public sealed class AnimeProjectFile
{
    public string Version { get; init; } = "1.0";
    public string InputPath { get; set; } = string.Empty;
    public string WorkingDirectory { get; set; } = string.Empty;
    public int? SelectedAudioTrackIndex { get; set; }
    public string WorkingAudioPath { get; set; } = string.Empty;
    public string TranscriptPath { get; set; } = string.Empty;
    public string SelectionPath { get; set; } = string.Empty;
    public string Status { get; set; } = "initialized";
    public DateTime CreatedAtUtc { get; init; } = DateTime.UtcNow;
    public DateTime UpdatedAtUtc { get; set; } = DateTime.UtcNow;
}
