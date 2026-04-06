namespace AnimeTranscoder.Models;

public sealed class SubtitleTrackInfo
{
    public int Index { get; init; }
    public string Title { get; init; } = string.Empty;
    public string Language { get; init; } = string.Empty;
    public bool IsDefault { get; init; }
    public string CodecName { get; init; } = string.Empty;
    public string TextSample { get; init; } = string.Empty;
    public string AnalysisSource { get; init; } = "ffprobe";

    public bool IsImageBased =>
        CodecName.Contains("pgs", StringComparison.OrdinalIgnoreCase) ||
        CodecName.Contains("dvd", StringComparison.OrdinalIgnoreCase) ||
        CodecName.Contains("dvb", StringComparison.OrdinalIgnoreCase) ||
        CodecName.Contains("xsub", StringComparison.OrdinalIgnoreCase) ||
        CodecName.Contains("vobsub", StringComparison.OrdinalIgnoreCase);

    public bool IsTextBased => !IsImageBased;

    public string SubtitleKindText => IsImageBased ? "图片字幕" : "文本字幕";
}
