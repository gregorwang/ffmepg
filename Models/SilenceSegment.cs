namespace AnimeTranscoder.Models;

public sealed class SilenceSegment
{
    public double StartSeconds { get; init; }
    public double EndSeconds { get; init; }
    public double DurationSeconds { get; init; }

    public string StartLabel => TimeSpan.FromSeconds(Math.Max(StartSeconds, 0)).ToString(@"hh\:mm\:ss\.fff");

    public string EndLabel => TimeSpan.FromSeconds(Math.Max(EndSeconds, 0)).ToString(@"hh\:mm\:ss\.fff");

    public string DurationLabel => $"{DurationSeconds:0.###} s";

    public string Summary => $"{StartLabel} -> {EndLabel} ({DurationLabel})";
}
