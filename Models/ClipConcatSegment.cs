using System.Globalization;

namespace AnimeTranscoder.Models;

public sealed class ClipConcatSegment
{
    public int Sequence { get; init; }
    public TimeSpan Start { get; init; }
    public TimeSpan Duration { get; init; }
    public TimeSpan End => Start + Duration;

    public string StartText => FormatTime(Start);
    public string DurationText => FormatTime(Duration);
    public string EndText => FormatTime(End);

    private static string FormatTime(TimeSpan value)
    {
        return value.ToString(@"hh\:mm\:ss\.fff", CultureInfo.InvariantCulture);
    }
}
