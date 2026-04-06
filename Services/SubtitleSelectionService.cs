using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class SubtitleSelectionService
{
    public int? SelectSubtitleTrackOrdinal(IReadOnlyList<SubtitleTrackInfo> subtitleTracks, string preference)
    {
        if (subtitleTracks.Count == 0)
        {
            return null;
        }

        var matchedTrack = subtitleTracks
            .OrderByDescending(track => ScoreTrack(track, preference))
            .ThenByDescending(track => track.IsDefault)
            .ThenBy(track => track.Index)
            .FirstOrDefault();

        return matchedTrack is null
            ? null
            : subtitleTracks
            .Select((track, ordinal) => new { track, ordinal })
            .First(item => item.track.Index == matchedTrack.Index)
            .ordinal;
    }

    public string BuildSubtitleKindSummary(IReadOnlyList<SubtitleTrackInfo> subtitleTracks)
    {
        if (subtitleTracks.Count == 0)
        {
            return "未检测到字幕";
        }

        var textCount = subtitleTracks.Count(track => track.IsTextBased);
        var imageCount = subtitleTracks.Count(track => track.IsImageBased);
        return $"文本字幕 {textCount} 条，图片字幕 {imageCount} 条";
    }

    private static int ScoreTrack(SubtitleTrackInfo track, string preference)
    {
        var score = 0;
        var haystack = $"{track.Title} {track.Language} {track.CodecName} {track.TextSample}";

        if (track.IsDefault)
        {
            score += 40;
        }

        if (track.IsTextBased)
        {
            score += 30;
        }
        else
        {
            score += 15;
        }

        if (ContainsAny(haystack, ["zh", "chi", "zho", "中文", "中日", "cn"]))
        {
            score += 35;
        }

        if (!string.IsNullOrWhiteSpace(track.TextSample))
        {
            score += 20;
        }

        score += preference switch
        {
            "chs" when ContainsAny(haystack, ["chs", "简体", "简中", "sc", "gb"]) => 60,
            "cht" when ContainsAny(haystack, ["cht", "繁體", "繁体", "tc", "big5"]) => 60,
            "default" when track.IsDefault => 50,
            _ => 0
        };

        if (ContainsAny(haystack, ["sign", "song", "karaoke"]))
        {
            score -= 30;
        }

        return score;
    }

    private static bool ContainsAny(string value, IEnumerable<string> keywords)
    {
        foreach (var keyword in keywords)
        {
            if (value.Contains(keyword, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }
}
