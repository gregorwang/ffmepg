using AnimeTranscoder.Models;
using AnimeTranscoder.Services;
using Xunit;

namespace AnimeTranscoder.Tests;

public sealed class FileProtocolRoundTripTests
{
    [Fact]
    public async Task AnimeProjectFile_RoundTripsThroughJson()
    {
        using var workspace = new TestWorkspace();
        var service = new ProjectFileService();
        var path = workspace.PathFor("project/demo.atproj");
        var document = new AnimeProjectFile
        {
            InputPath = workspace.CreateTextFile("media/input.mp4"),
            WorkingDirectory = workspace.PathFor("project/demo.artifacts"),
            SelectedAudioTrackIndex = 2,
            WorkingAudioPath = workspace.PathFor("project/demo.artifacts/work-audio.wav"),
            TranscriptPath = workspace.PathFor("project/demo.artifacts/transcript.json"),
            SelectionPath = workspace.PathFor("project/demo.artifacts/selection.json"),
            Status = "unicode-阶段二",
            UpdatedAtUtc = new DateTime(2026, 4, 11, 10, 20, 30, DateTimeKind.Utc)
        };

        await service.SaveAsync(path, document);
        var roundTripped = await service.LoadAsync(path);

        Assert.Equal(document.InputPath, roundTripped.InputPath);
        Assert.Equal(document.WorkingDirectory, roundTripped.WorkingDirectory);
        Assert.Equal(document.SelectedAudioTrackIndex, roundTripped.SelectedAudioTrackIndex);
        Assert.Equal(document.WorkingAudioPath, roundTripped.WorkingAudioPath);
        Assert.Equal(document.TranscriptPath, roundTripped.TranscriptPath);
        Assert.Equal(document.SelectionPath, roundTripped.SelectionPath);
        Assert.Equal(document.Status, roundTripped.Status);
    }

    [Fact]
    public async Task TranscriptDocument_RoundTripsThroughJson()
    {
        using var workspace = new TestWorkspace();
        var service = new TranscriptDocumentService();
        var path = workspace.PathFor("protocol/transcript.json");
        var document = new TranscriptDocument
        {
            MediaPath = "C:/视频/第01集.mkv",
            AudioPath = "C:/音频/work-audio.wav",
            Segments =
            [
                new TranscriptSegment
                {
                    Id = "seg_001",
                    Start = -0.25,
                    End = 0.00,
                    Text = "こんにちは",
                    Language = "ja",
                    Speaker = "A",
                    Confidence = 0.98,
                    Source = "whisper.cpp",
                    Overlap = false,
                    Channel = "mono"
                },
                new TranscriptSegment
                {
                    Id = "seg_002",
                    Start = 12.5,
                    End = 12.5,
                    Text = "zero-duration",
                    Language = "en",
                    Speaker = null,
                    Confidence = 0.0,
                    Source = "manual",
                    Overlap = true,
                    Channel = "dual"
                }
            ]
        };

        await service.SaveAsync(path, document);
        var roundTripped = await service.LoadAsync(path);

        Assert.Equal(document.MediaPath, roundTripped.MediaPath);
        Assert.Equal(document.AudioPath, roundTripped.AudioPath);
        Assert.Equal(document.Segments.Count, roundTripped.Segments.Count);
        Assert.Collection(roundTripped.Segments,
            item =>
            {
                Assert.Equal("seg_001", item.Id);
                Assert.Equal(-0.25, item.Start, 3);
                Assert.Equal(0.00, item.End, 3);
                Assert.Equal("こんにちは", item.Text);
                Assert.Equal("ja", item.Language);
                Assert.Equal("A", item.Speaker);
                Assert.NotNull(item.Confidence);
                Assert.Equal(0.98, item.Confidence!.Value, 3);
                Assert.Equal("whisper.cpp", item.Source);
                Assert.False(item.Overlap);
                Assert.Equal("mono", item.Channel);
            },
            item =>
            {
                Assert.Equal("seg_002", item.Id);
                Assert.Equal(12.5, item.Start, 3);
                Assert.Equal(12.5, item.End, 3);
                Assert.Equal("zero-duration", item.Text);
                Assert.Equal("en", item.Language);
                Assert.Null(item.Speaker);
                Assert.NotNull(item.Confidence);
                Assert.Equal(0.0, item.Confidence!.Value, 3);
                Assert.Equal("manual", item.Source);
                Assert.True(item.Overlap);
                Assert.Equal("dual", item.Channel);
            });
    }

    [Fact]
    public async Task SelectionDocument_RoundTripsThroughJson()
    {
        using var workspace = new TestWorkspace();
        var service = new SelectionDocumentService();
        var path = workspace.PathFor("protocol/selection.json");
        var document = new SelectionDocument
        {
            TranscriptVersion = "1.0-beta",
            DecisionSource = "外部代理",
            ConflictPolicy = "exclude_wins",
            TargetSegments =
            [
                new SelectionTargetSegment
                {
                    SegmentId = "seg_001",
                    Action = SelectionAction.Keep,
                    Reason = "保留台词"
                },
                new SelectionTargetSegment
                {
                    SegmentId = "seg_002",
                    Action = SelectionAction.Uncertain,
                    Reason = "0ms edge"
                }
            ]
        };

        await service.SaveAsync(path, document);
        var roundTripped = await service.LoadAsync(path);

        Assert.Equal(document.TranscriptVersion, roundTripped.TranscriptVersion);
        Assert.Equal(document.DecisionSource, roundTripped.DecisionSource);
        Assert.Equal(document.ConflictPolicy, roundTripped.ConflictPolicy);
        Assert.Equal(document.TargetSegments.Count, roundTripped.TargetSegments.Count);
        Assert.Collection(roundTripped.TargetSegments,
            item =>
            {
                Assert.Equal("seg_001", item.SegmentId);
                Assert.Equal(SelectionAction.Keep, item.Action);
                Assert.Equal("保留台词", item.Reason);
            },
            item =>
            {
                Assert.Equal("seg_002", item.SegmentId);
                Assert.Equal(SelectionAction.Uncertain, item.Action);
                Assert.Equal("0ms edge", item.Reason);
            });
    }
}
