using System.Globalization;

namespace AnimeTranscoder.Models;

public sealed class HighlightCandidate
{
    public int Rank { get; init; }
    public double StartSeconds { get; init; }
    public double EndSeconds { get; init; }
    public double DurationSeconds { get; init; }
    public double Score { get; init; }
    public double SceneChangeRate { get; init; }
    public double VolumeLevel { get; init; }
    public bool IsBlackFiltered { get; init; }
    public bool IsFreezeFiltered { get; init; }

    public string TimeRangeLabel =>
        $"{FormatTime(StartSeconds)} - {FormatTime(EndSeconds)}";

    public string DurationLabel =>
        $"{DurationSeconds:0.#}s";

    public string ScoreLabel =>
        $"{Score:0.0}";

    public string SceneRateLabel =>
        $"{SceneChangeRate:0.##}/s";

    public string VolumeLevelLabel =>
        double.IsNegativeInfinity(VolumeLevel) ? "-∞ dB" : $"{VolumeLevel:0.#} dB";

    public string FilterLabel =>
        IsBlackFiltered || IsFreezeFiltered
            ? string.Join(" ", IsBlackFiltered ? "🖤黑场" : "", IsFreezeFiltered ? "❄冻帧" : "").Trim()
            : "—";

    public string Summary =>
        $"#{Rank} {TimeRangeLabel} | {DurationLabel} | 评分 {ScoreLabel}";

    private static string FormatTime(double seconds) =>
        TimeSpan.FromSeconds(Math.Max(seconds, 0))
            .ToString(@"hh\:mm\:ss\.f", CultureInfo.InvariantCulture);
}
