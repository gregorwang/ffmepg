namespace AnimeTranscoder.Models;

public sealed class TranscodeTaskSpec
{
    public Guid TaskId { get; init; }
    public string InputPath { get; init; } = string.Empty;
    public string OutputPath { get; init; } = string.Empty;
    public string Preset { get; init; } = "default";
    public bool? DeleteSource { get; init; }
    public bool NoOverlay { get; init; }
    public string DanmakuInputPath { get; init; } = string.Empty;
    public string DanmakuExcludedCommentKeys { get; init; } = string.Empty;

    public string FileName => Path.GetFileName(InputPath);
}
