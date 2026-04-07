using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class BilibiliCidResolverService
{
    public BangumiEpisodeInfo ResolveEpisode(
        BangumiSeasonInfo season,
        AnimeEpisodeMatch match,
        DanmakuTitleMappingEntry? mappingOverride,
        Action<string>? logCallback)
    {
        var mainEpisodes = season.Episodes.Where(episode => episode.SectionType == 0).ToList();
        var episodePool = mainEpisodes.Count > 0 ? mainEpisodes : season.Episodes;
        if (episodePool.Count == 0)
        {
            throw new InvalidOperationException($"番剧详情未返回可用分集：{season.Title}");
        }

        var episodeOverride = mappingOverride?.EpisodeOverrides
            .FirstOrDefault(overrideItem => overrideItem.EpisodeNumber == match.EpisodeNumber);

        if (episodeOverride?.Cid is > 0)
        {
            logCallback?.Invoke($"CID 解析命中本地配置：EP{match.EpisodeNumber} -> cid={episodeOverride.Cid.Value}");
            return new BangumiEpisodeInfo
            {
                EpisodeId = episodeOverride.EpisodeId ?? 0,
                Cid = episodeOverride.Cid.Value,
                Number = match.EpisodeNumber,
                ShowTitle = $"第{match.EpisodeNumber}话"
            };
        }

        BangumiEpisodeInfo? matchedEpisode = null;
        if (episodeOverride?.EpisodeId is > 0)
        {
            matchedEpisode = episodePool.FirstOrDefault(episode => episode.EpisodeId == episodeOverride.EpisodeId.Value);
        }

        matchedEpisode ??= episodePool.FirstOrDefault(episode => episode.Number == match.EpisodeNumber);

        if (matchedEpisode is null && !string.IsNullOrWhiteSpace(episodeOverride?.TitleContains))
        {
            matchedEpisode = episodePool.FirstOrDefault(episode =>
                episode.ShowTitle.Contains(episodeOverride.TitleContains, StringComparison.OrdinalIgnoreCase) ||
                episode.LongTitle.Contains(episodeOverride.TitleContains, StringComparison.OrdinalIgnoreCase));
        }

        if (matchedEpisode is null)
        {
            matchedEpisode = episodePool.FirstOrDefault(episode =>
                episode.ShowTitle.Contains($"第{match.EpisodeNumber}", StringComparison.OrdinalIgnoreCase) ||
                episode.ShareCopy.Contains($"第{match.EpisodeNumber}", StringComparison.OrdinalIgnoreCase));
        }

        if (matchedEpisode is null)
        {
            throw new InvalidOperationException($"未在番剧 {season.Title} 中找到第 {match.EpisodeNumber} 集。");
        }

        if (matchedEpisode.Cid <= 0)
        {
            throw new InvalidOperationException($"已匹配分集，但缺少可用 cid：{matchedEpisode.ShowTitle}");
        }

        logCallback?.Invoke($"CID 解析完成：{season.Title} EP{match.EpisodeNumber} -> cid={matchedEpisode.Cid}");
        return matchedEpisode;
    }
}
