namespace AnimeTranscoder.Models;

public sealed class VolumeSegment
{
    public double StartSeconds { get; init; }
    public double EndSeconds { get; init; }
    public double MeanVolumeDb { get; init; }
    public double PeakVolumeDb { get; init; }

    public string StartLabel => $"{StartSeconds:0.000}s";
    public string EndLabel => $"{EndSeconds:0.000}s";
    public string MeanLabel => double.IsNegativeInfinity(MeanVolumeDb) ? "-∞ dB" : $"{MeanVolumeDb:0.#} dB";
    public string Summary => $"{StartLabel} - {EndLabel} | 均值 {MeanLabel}";
}
