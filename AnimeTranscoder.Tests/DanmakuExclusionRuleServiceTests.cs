using AnimeTranscoder.Models;
using AnimeTranscoder.Services;
using Xunit;

namespace AnimeTranscoder.Tests;

public sealed class DanmakuExclusionRuleServiceTests
{
    [Fact]
    public async Task ExportAndImportAsync_Json_RoundTripsExcludedKeys()
    {
        var service = new DanmakuExclusionRuleService();
        var tempDirectory = Path.Combine(Path.GetTempPath(), "AnimeTranscoderTests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempDirectory);
        var path = Path.Combine(tempDirectory, "rules.json");

        var job = new TranscodeJob
        {
            InputPath = @"C:\anime\episode01.mkv"
        };
        job.DanmakuXmlPath = @"C:\anime\episode01.xml";
        job.DanmakuAssPath = @"C:\anime\episode01.ass";

        var excludedKeys = new[] { "1.000|1|foo", "2.000|5|bar" };
        await service.ExportAsync(path, job, excludedKeys);

        var imported = await service.ImportAsync(path);

        Assert.Equal(2, imported.Count);
        Assert.Contains("1.000|1|foo", imported);
        Assert.Contains("2.000|5|bar", imported);
    }

    [Fact]
    public async Task ExportAndImportAsync_Text_RoundTripsExcludedKeys()
    {
        var service = new DanmakuExclusionRuleService();
        var tempDirectory = Path.Combine(Path.GetTempPath(), "AnimeTranscoderTests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempDirectory);
        var path = Path.Combine(tempDirectory, "rules.txt");

        var job = new TranscodeJob
        {
            InputPath = @"C:\anime\episode01.mkv"
        };

        var excludedKeys = new[] { "1.000|1|foo", "2.000|5|bar" };
        await service.ExportAsync(path, job, excludedKeys);

        var imported = await service.ImportAsync(path);

        Assert.Equal(2, imported.Count);
        Assert.Contains("1.000|1|foo", imported);
        Assert.Contains("2.000|5|bar", imported);
    }
}
