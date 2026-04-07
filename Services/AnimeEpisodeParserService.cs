using System.Text;
using System.Text.RegularExpressions;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class AnimeEpisodeParserService
{
    private static readonly Regex LeadingBracketGroupRegex = new(@"^\s*[\[\【][^\]\】]+[\]\】]\s*", RegexOptions.Compiled);
    private static readonly Regex SeasonRegex = new(
        @"(?ix)
        (?:
            \bS(?<season>\d{1,2})\b |
            \bSeason\s*(?<season>\d{1,2})\b |
            \b(?<season>\d{1,2})(?:st|nd|rd|th)\s+Season\b |
            第\s*(?<season>\d{1,2})\s*季
        )",
        RegexOptions.Compiled);
    private static readonly Regex[] EpisodeRegexes =
    [
        new Regex(@"(?ix)\bS(?<season>\d{1,2})E(?<episode>\d{1,3})\b", RegexOptions.Compiled),
        new Regex(@"第\s*(?<episode>\d{1,3})\s*[话話集]", RegexOptions.Compiled),
        new Regex(@"(?ix)\bEP?\s*(?<episode>\d{1,3})\b", RegexOptions.Compiled),
        new Regex(@"(?ix)(?:\s-\s|\s)\b(?<episode>\d{1,3})(?:v\d+)?(?=(?:\s|$|[\[\(]))", RegexOptions.Compiled),
        new Regex(@"(?ix)[\[\(](?<episode>\d{1,3})(?:v\d+)?[\]\)]", RegexOptions.Compiled)
    ];

    public AnimeEpisodeMatch Parse(string inputPath)
    {
        var inputFileName = Path.GetFileName(inputPath);
        var fileName = Path.GetFileNameWithoutExtension(inputPath);
        if (string.IsNullOrWhiteSpace(fileName))
        {
            throw new InvalidOperationException("输入文件名为空，无法识别番名和集号。");
        }

        var candidate = fileName.Trim();
        while (LeadingBracketGroupRegex.IsMatch(candidate))
        {
            candidate = LeadingBracketGroupRegex.Replace(candidate, string.Empty, 1);
        }

        Match? selectedEpisodeMatch = null;
        foreach (var regex in EpisodeRegexes)
        {
            var match = regex.Match(candidate);
            if (match.Success)
            {
                selectedEpisodeMatch = match;
                break;
            }
        }

        if (selectedEpisodeMatch is null ||
            !int.TryParse(selectedEpisodeMatch.Groups["episode"].Value, out var episodeNumber) ||
            episodeNumber <= 0)
        {
            throw new InvalidOperationException($"无法从文件名中识别集号：{inputFileName}");
        }

        var titleSegment = CleanupTitleSegment(candidate[..selectedEpisodeMatch.Index], keepSeasonMarker: false);
        if (string.IsNullOrWhiteSpace(titleSegment))
        {
            throw new InvalidOperationException($"无法从文件名中识别番名：{inputFileName}");
        }

        int? seasonNumber = null;
        if (selectedEpisodeMatch.Groups["season"].Success &&
            int.TryParse(selectedEpisodeMatch.Groups["season"].Value, out var seasonFromEpisodeToken))
        {
            seasonNumber = seasonFromEpisodeToken;
        }

        var seasonMatch = SeasonRegex.Match(candidate);
        if (seasonNumber is null &&
            seasonMatch.Success &&
            int.TryParse(seasonMatch.Groups["season"].Value, out var seasonFromTitle))
        {
            seasonNumber = seasonFromTitle;
        }

        var searchKeyword = CleanupTitleSegment(candidate[..selectedEpisodeMatch.Index], keepSeasonMarker: true);
        if (seasonNumber is not null &&
            !searchKeyword.Contains($"Season {seasonNumber}", StringComparison.OrdinalIgnoreCase) &&
            !searchKeyword.Contains($"S{seasonNumber}", StringComparison.OrdinalIgnoreCase) &&
            !searchKeyword.Contains($"第{seasonNumber}季", StringComparison.OrdinalIgnoreCase))
        {
            searchKeyword = $"{searchKeyword} Season {seasonNumber}";
        }

        return new AnimeEpisodeMatch
        {
            InputFileName = inputFileName,
            RawTitle = titleSegment,
            NormalizedTitle = NormalizeForMatch(titleSegment),
            SearchKeyword = searchKeyword,
            EpisodeNumber = episodeNumber,
            SeasonNumber = seasonNumber,
            EpisodeToken = selectedEpisodeMatch.Value
        };
    }

    public static string NormalizeForMatch(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        var normalized = value.Normalize(NormalizationForm.FormKC).ToLowerInvariant();
        normalized = Regex.Replace(normalized, @"[^\p{L}\p{N}]+", " ");
        return Regex.Replace(normalized, @"\s+", " ").Trim();
    }

    private static string CleanupTitleSegment(string value, bool keepSeasonMarker)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        var cleaned = value.Replace('_', ' ').Replace('.', ' ').Trim();
        cleaned = Regex.Replace(cleaned, @"[\[\(【].*?[\]\)】]", " ");
        cleaned = Regex.Replace(cleaned, @"(?ix)\b(1080p|2160p|720p|x264|x265|hevc|aac|flac|webrip|web\-dl|baha|bilibili|nf|amzn|cr|at\-x|10bit|8bit)\b", " ");
        cleaned = Regex.Replace(cleaned, @"(?ix)\b(v\d+)\b", " ");

        if (!keepSeasonMarker)
        {
            cleaned = SeasonRegex.Replace(cleaned, " ");
        }

        cleaned = cleaned.Trim(' ', '-', '_');
        return Regex.Replace(cleaned, @"\s+", " ").Trim();
    }
}
