using AnimeTranscoder.Models;
using AnimeTranscoder.Services;
using Xunit;

namespace AnimeTranscoder.Tests;

public sealed class ClipCommandBuilderTests
{
    [Fact]
    public void BuildConcatFilterComplex_IncludesConcatGraph()
    {
        var builder = new ClipCommandBuilder();
        var segments = new[]
        {
            new ClipConcatSegment { Start = TimeSpan.FromSeconds(1), Duration = TimeSpan.FromSeconds(2) },
            new ClipConcatSegment { Start = TimeSpan.FromSeconds(5), Duration = TimeSpan.FromSeconds(3) }
        };

        var filter = builder.BuildConcatFilterComplex(segments, includeAudio: true);

        Assert.Contains("[0:v:0]trim=start=1:end=3,setpts=PTS-STARTPTS[v0]", filter, StringComparison.Ordinal);
        Assert.Contains("[0:a:0]atrim=start=5:end=8,asetpts=PTS-STARTPTS[a1]", filter, StringComparison.Ordinal);
        Assert.Contains("concat=n=2:v=1:a=1[vout][aout]", filter, StringComparison.Ordinal);
    }

    [Fact]
    public void BuildConcatArguments_WithScriptPath_UsesFilterComplexScript()
    {
        var builder = new ClipCommandBuilder();
        var segments = new[]
        {
            new ClipConcatSegment { Start = TimeSpan.Zero, Duration = TimeSpan.FromSeconds(2) }
        };

        var args = builder.BuildConcatArguments(
            @"C:\in.mp4",
            @"C:\out.mp4",
            segments,
            includeAudio: true,
            videoEncoder: "h264_nvenc",
            nvencPreset: "p4",
            cq: 30,
            audioBitrateKbps: 128,
            filterComplexScriptPath: @"C:\temp\concat-filter.txt");

        Assert.DoesNotContain("-filter_complex", args);
        var index = args.ToList().IndexOf("-filter_complex_script");
        Assert.True(index >= 0);
        Assert.Equal(@"C:\temp\concat-filter.txt", args[index + 1]);
    }
}
