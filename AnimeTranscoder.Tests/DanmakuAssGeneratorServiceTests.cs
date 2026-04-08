using AnimeTranscoder.Models;
using AnimeTranscoder.Services;
using Xunit;

namespace AnimeTranscoder.Tests;

public sealed class DanmakuAssGeneratorServiceTests
{
    [Fact]
    public void ParseComments_FiltersSpecialAndBlockedContent()
    {
        var settings = AppSettings.CreateDefault(Path.GetTempPath());
        settings.DanmakuBlockKeywords = "屏蔽词";
        settings.DanmakuFilterSpecialTypes = true;
        settings.DanmakuTimeOffsetSeconds = 1.5;
        settings.DanmakuDensity = 1;

        var service = new DanmakuAssGeneratorService(new DanmakuCacheService());
        const string xml =
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?><i>" +
            "<d p=\"1.0,1,25,16777215,0,0,0,0\">hello</d>" +
            "<d p=\"2.0,7,25,16711680,0,0,0,0\">special</d>" +
            "<d p=\"3.0,5,25,16777215,0,0,0,0\">屏蔽词 test</d>" +
            "</i>";

        var comments = service.ParseComments(xml, settings);

        var comment = Assert.Single(comments);
        Assert.Equal(2.5, comment.TimeSeconds, 3);
        Assert.Equal("hello", comment.Content);
    }

    [Fact]
    public void BuildAssDocument_GeneratesDialogueLines()
    {
        var settings = AppSettings.CreateDefault(Path.GetTempPath());
        settings.DanmakuFontSize = 40;
        settings.DanmakuDensity = 1;

        var service = new DanmakuAssGeneratorService(new DanmakuCacheService());
        var ass = service.BuildAssDocument(
        [
            new DanmakuComment { TimeSeconds = 1.2, Mode = 1, FontSize = 25, Color = 16777215, Content = "first" },
            new DanmakuComment { TimeSeconds = 2.4, Mode = 5, FontSize = 25, Color = 16711680, Content = "top" }
        ],
        settings);

        Assert.Contains("Style: Danmaku", ass, StringComparison.Ordinal);
        Assert.Contains("Dialogue: 0,0:00:01.20", ass, StringComparison.Ordinal);
        Assert.Contains(@"\move(", ass, StringComparison.Ordinal);
        Assert.Contains(@"\an8\pos(", ass, StringComparison.Ordinal);
    }

    [Fact]
    public void BuildAssDocument_UpperHalfMode_KeepsBottomDanmakuAwayFromVideoBottom()
    {
        var settings = AppSettings.CreateDefault(Path.GetTempPath());
        settings.BurnEmbeddedSubtitles = true;
        settings.DanmakuAreaMode = DanmakuAreaModes.UpperHalf;
        settings.DanmakuFontSize = 40;

        var service = new DanmakuAssGeneratorService(new DanmakuCacheService());
        var ass = service.BuildAssDocument(
        [
            new DanmakuComment { TimeSeconds = 2.0, Mode = 4, FontSize = 25, Color = 16777215, Content = "bottom" }
        ],
        settings);

        Assert.Contains(@"\an2\pos(960,520)", ass, StringComparison.Ordinal);
    }

    [Fact]
    public void ParseComments_ExcludesManualCommentKeys()
    {
        var settings = AppSettings.CreateDefault(Path.GetTempPath());
        var service = new DanmakuAssGeneratorService(new DanmakuCacheService());
        const string xml =
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?><i>" +
            "<d p=\"1.0,1,25,16777215,0,0,0,0\">keep</d>" +
            "<d p=\"2.0,1,25,16777215,0,0,0,0\">remove</d>" +
            "</i>";

        var excludedKeys = new HashSet<string>(StringComparer.Ordinal)
        {
            DanmakuAssGeneratorService.BuildCommentKey(2.0, 1, "remove")
        };

        var comments = service.ParseComments(xml, settings, excludedKeys);

        var comment = Assert.Single(comments);
        Assert.Equal("keep", comment.Content);
    }
}
