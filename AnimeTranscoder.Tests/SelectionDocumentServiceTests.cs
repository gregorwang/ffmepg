using AnimeTranscoder.Models;
using AnimeTranscoder.Services;
using Xunit;

namespace AnimeTranscoder.Tests;

public sealed class SelectionDocumentServiceTests
{
    [Fact]
    public void ResolveKeepIntervals_ExcludeWinsConflictPolicyDropsConflictedSegment()
    {
        var transcript = new TranscriptDocument
        {
            Segments =
            [
                new TranscriptSegment { Id = "seg-1", Start = 1.0, End = 2.0, Text = "a", Source = "test" },
                new TranscriptSegment { Id = "seg-2", Start = 3.0, End = 4.0, Text = "b", Source = "test" }
            ]
        };

        var selection = new SelectionDocument
        {
            ConflictPolicy = "exclude_wins",
            TargetSegments =
            [
                new SelectionTargetSegment { SegmentId = "seg-1", Action = SelectionAction.Keep, Reason = "keep" },
                new SelectionTargetSegment { SegmentId = "seg-1", Action = SelectionAction.Exclude, Reason = "drop" },
                new SelectionTargetSegment { SegmentId = "seg-2", Action = SelectionAction.Keep, Reason = "keep" }
            ]
        };

        var keepIntervals = AudioSelectionRenderService.ResolveKeepIntervals(transcript, selection);

        var interval = Assert.Single(keepIntervals);
        Assert.Equal(3.0, interval.Start, 3);
        Assert.Equal(4.0, interval.End, 3);
    }

    [Fact]
    public void Validate_AllowsEmptyTargetSegments()
    {
        var document = new SelectionDocument();

        SelectionDocumentService.Validate(document);
    }
}
