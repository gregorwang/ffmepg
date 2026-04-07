using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class BangumiMappingService
{
    private readonly BilibiliBangumiClient _client;

    public BangumiMappingService(BilibiliBangumiClient client)
    {
        _client = client;
    }

    public async Task<BangumiSeasonInfo> ResolveSeasonAsync(
        AnimeEpisodeMatch match,
        DanmakuTitleMappingEntry? mappingOverride,
        Action<string>? logCallback,
        CancellationToken cancellationToken = default)
    {
        if (mappingOverride?.SeasonId is > 0)
        {
            logCallback?.Invoke($"番剧映射命中本地配置：{mappingOverride.Name} -> season_id={mappingOverride.SeasonId.Value}");
            return await _client.GetSeasonDetailAsync(mappingOverride.SeasonId.Value, cancellationToken);
        }

        var keyword = string.IsNullOrWhiteSpace(mappingOverride?.SearchKeyword)
            ? match.SearchKeyword
            : mappingOverride.SearchKeyword;

        var candidates = await _client.SearchSeasonsAsync(keyword, cancellationToken);
        if (candidates.Count == 0)
        {
            throw new InvalidOperationException($"未搜索到匹配番剧：{keyword}");
        }

        var bestCandidate = candidates
            .Select(candidate => new { Candidate = candidate, Score = ScoreCandidate(match, candidate) })
            .OrderByDescending(item => item.Score)
            .ThenByDescending(item => item.Candidate.EpisodeCount)
            .Select(item => item.Candidate)
            .First();

        logCallback?.Invoke($"番剧映射完成：{keyword} -> {bestCandidate.Title} (season_id={bestCandidate.SeasonId})");
        return await _client.GetSeasonDetailAsync(bestCandidate.SeasonId, cancellationToken);
    }

    private static int ScoreCandidate(AnimeEpisodeMatch match, BangumiSeasonInfo candidate)
    {
        var normalizedQuery = match.NormalizedTitle;
        var normalizedTitle = AnimeEpisodeParserService.NormalizeForMatch(candidate.Title);
        var normalizedOriginal = AnimeEpisodeParserService.NormalizeForMatch(candidate.OriginalTitle);
        var score = 0;

        score = Math.Max(score, ScoreSingle(normalizedQuery, normalizedTitle));
        score = Math.Max(score, ScoreSingle(normalizedQuery, normalizedOriginal));

        if (!string.IsNullOrWhiteSpace(match.SearchKeyword))
        {
            var normalizedKeyword = AnimeEpisodeParserService.NormalizeForMatch(match.SearchKeyword);
            score = Math.Max(score, ScoreSingle(normalizedKeyword, normalizedTitle) - 10);
            score = Math.Max(score, ScoreSingle(normalizedKeyword, normalizedOriginal) - 10);
        }

        if (candidate.Title.Contains("中配", StringComparison.OrdinalIgnoreCase) ||
            candidate.Title.Contains("国语", StringComparison.OrdinalIgnoreCase))
        {
            score -= 35;
        }

        if (candidate.EpisodeCount > 0)
        {
            score += Math.Min(candidate.EpisodeCount, 60) / 3;
        }

        return score;
    }

    private static int ScoreSingle(string query, string candidate)
    {
        if (string.IsNullOrWhiteSpace(query) || string.IsNullOrWhiteSpace(candidate))
        {
            return 0;
        }

        if (string.Equals(query, candidate, StringComparison.Ordinal))
        {
            return 320;
        }

        if (candidate.Contains(query, StringComparison.Ordinal) ||
            query.Contains(candidate, StringComparison.Ordinal))
        {
            return 220;
        }

        var queryTokens = query.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        var candidateTokens = candidate.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        var overlap = queryTokens.Intersect(candidateTokens, StringComparer.Ordinal).Count();
        return overlap * 28;
    }
}
