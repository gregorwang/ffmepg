using AnimeTranscoder.Models;
using AnimeTranscoder.Services;
using Xunit;

namespace AnimeTranscoder.Tests;

public sealed class FfmpegCommandBuilderTests
{
    [Fact]
    public void BuildArguments_WithEmbeddedSubtitleAndDanmaku_CombinesFilters()
    {
        var builder = new FfmpegCommandBuilder();
        var settings = AppSettings.CreateDefault(Path.GetTempPath());

        var args = builder.BuildArguments(
            @"C:\anime\episode01.mkv",
            @"C:\out\episode01.mp4",
            2,
            @"C:\danmaku\episode01.ass",
            settings,
            "libx264");

        var filterIndex = args.ToList().IndexOf("-vf");
        Assert.True(filterIndex >= 0);
        Assert.Contains("subtitles='C\\:/anime/episode01.mkv':si=2,ass='C\\:/danmaku/episode01.ass'", args[filterIndex + 1], StringComparison.Ordinal);
    }
}
