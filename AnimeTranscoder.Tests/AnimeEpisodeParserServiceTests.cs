using AnimeTranscoder.Services;
using Xunit;

namespace AnimeTranscoder.Tests;

public sealed class AnimeEpisodeParserServiceTests
{
    private readonly AnimeEpisodeParserService _service = new();

    [Fact]
    public void Parse_CommonFansubFilename_ReturnsTitleAndEpisode()
    {
        var result = _service.Parse(@"C:\anime\[SubsPlease] Sousou no Frieren - 03 (1080p) [A1B2C3D4].mkv");

        Assert.Equal("Sousou no Frieren", result.RawTitle);
        Assert.Equal(3, result.EpisodeNumber);
        Assert.Equal("sousou no frieren", result.NormalizedTitle);
    }

    [Fact]
    public void Parse_ChineseSeasonFilename_ReturnsSeasonAndEpisode()
    {
        var result = _service.Parse(@"C:\anime\葬送的芙莉莲 第2季 第05话.mkv");

        Assert.Equal("葬送的芙莉莲", result.RawTitle);
        Assert.Equal(2, result.SeasonNumber);
        Assert.Equal(5, result.EpisodeNumber);
    }
}
