namespace AnimeTranscoder.Models;

public sealed class AudioTrackInfo
{
    public int Index { get; init; }
    public int StreamIndex { get; init; }
    public string CodecName { get; init; } = string.Empty;
    public string Language { get; init; } = string.Empty;
    public string Title { get; init; } = string.Empty;
    public int Channels { get; init; }
    public string ChannelLayout { get; init; } = string.Empty;
    public int SampleRate { get; init; }
    public long BitRate { get; init; }
    public bool IsDefault { get; init; }

    public int DisplayIndex => Index + 1;

    public string Summary =>
        string.IsNullOrWhiteSpace(Title)
            ? $"{(IsDefault ? "[默认] " : string.Empty)}音轨 {DisplayIndex} | {LanguageLabel} | {CodecName} {ChannelSummary} {SampleRate}Hz"
            : $"{(IsDefault ? "[默认] " : string.Empty)}音轨 {DisplayIndex} | {LanguageLabel} | {Title} ({CodecName} {ChannelSummary} {SampleRate}Hz)";

    public string LanguageLabel =>
        string.IsNullOrWhiteSpace(Language) ? "未知" : Language;

    public string BitRateLabel =>
        BitRate > 0 ? $"{BitRate / 1000}k" : "未知";

    public string ChannelSummary =>
        Channels <= 0
            ? "未知"
            : string.IsNullOrWhiteSpace(ChannelLayout)
                ? $"{Channels}ch"
                : $"{Channels}ch/{ChannelLayout}";
}
