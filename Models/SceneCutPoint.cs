using System.Globalization;

namespace AnimeTranscoder.Models;

public sealed class SceneCutPoint
{
    public int Sequence { get; init; }
    public double TimeSeconds { get; init; }

    public string TimeText => TimeSpan
        .FromSeconds(Math.Max(TimeSeconds, 0))
        .ToString(@"hh\:mm\:ss\.fff", CultureInfo.InvariantCulture);
}
