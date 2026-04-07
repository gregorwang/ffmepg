using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class DanmakuPreparationService
{
    private readonly AnimeEpisodeParserService _parserService;
    private readonly DanmakuMappingConfigService _mappingConfigService;
    private readonly BangumiMappingService _bangumiMappingService;
    private readonly BilibiliCidResolverService _cidResolverService;
    private readonly DanmakuXmlService _xmlService;
    private readonly DanmakuAssGeneratorService _assGeneratorService;

    public DanmakuPreparationService(
        AnimeEpisodeParserService parserService,
        DanmakuMappingConfigService mappingConfigService,
        BangumiMappingService bangumiMappingService,
        BilibiliCidResolverService cidResolverService,
        DanmakuXmlService xmlService,
        DanmakuAssGeneratorService assGeneratorService)
    {
        _parserService = parserService;
        _mappingConfigService = mappingConfigService;
        _bangumiMappingService = bangumiMappingService;
        _cidResolverService = cidResolverService;
        _xmlService = xmlService;
        _assGeneratorService = assGeneratorService;
    }

    public async Task<DanmakuPreparationResult> PrepareAsync(
        string inputPath,
        AppSettings settings,
        Action<string>? logCallback,
        CancellationToken cancellationToken = default)
    {
        AnimeEpisodeMatch? match = null;
        BangumiSeasonInfo? season = null;
        BangumiEpisodeInfo? episode = null;
        string? xmlPath = null;
        var xmlCommentCount = 0;

        try
        {
            match = _parserService.Parse(inputPath);
            logCallback?.Invoke($"番名匹配完成：{match.RawTitle} | EP{match.EpisodeNumber}");
        }
        catch (Exception ex)
        {
            return Fail("番名匹配", ex.Message, match, season, episode, xmlPath);
        }

        DanmakuTitleMappingEntry? mappingOverride = null;
        try
        {
            var config = await _mappingConfigService.LoadAsync(settings.DanmakuMappingPath, cancellationToken);
            mappingOverride = _mappingConfigService.FindBestMatch(match, config);
            if (mappingOverride is not null)
            {
                logCallback?.Invoke($"番剧映射命中配置：{mappingOverride.Name}");
            }
        }
        catch (Exception ex)
        {
            return Fail("番剧映射", ex.Message, match, season, episode, xmlPath);
        }

        try
        {
            season = await _bangumiMappingService.ResolveSeasonAsync(match, mappingOverride, logCallback, cancellationToken);
        }
        catch (Exception ex)
        {
            return Fail("番剧映射", ex.Message, match, season, episode, xmlPath);
        }

        try
        {
            episode = _cidResolverService.ResolveEpisode(season, match, mappingOverride, logCallback);
        }
        catch (Exception ex)
        {
            return Fail("cid 解析", ex.Message, match, season, episode, xmlPath);
        }

        try
        {
            (xmlPath, xmlCommentCount) = await _xmlService.DownloadAsync(episode.Cid, logCallback, cancellationToken);
        }
        catch (Exception ex)
        {
            return Fail("XML 下载", ex.Message, match, season, episode, xmlPath);
        }

        try
        {
            var (assPath, assCommentCount) = await _assGeneratorService.GenerateAsync(
                episode.Cid,
                xmlPath!,
                settings,
                logCallback,
                cancellationToken);

            return new DanmakuPreparationResult
            {
                Success = true,
                EpisodeMatch = match,
                Season = season,
                Episode = episode,
                XmlPath = xmlPath!,
                AssPath = assPath,
                XmlCommentCount = xmlCommentCount,
                AssCommentCount = assCommentCount,
                Source = "bilibili-danmaku",
                KindSummary = $"Bilibili XML {xmlCommentCount} 条 -> ASS {assCommentCount} 条",
                Summary = $"{season.Title} 第{match.EpisodeNumber}集 | cid={episode.Cid} | XML {xmlCommentCount} 条 | ASS {assCommentCount} 条"
            };
        }
        catch (Exception ex)
        {
            return Fail("ASS 生成", ex.Message, match, season, episode, xmlPath);
        }
    }

    private static DanmakuPreparationResult Fail(
        string stage,
        string errorMessage,
        AnimeEpisodeMatch? match,
        BangumiSeasonInfo? season,
        BangumiEpisodeInfo? episode,
        string? xmlPath)
    {
        return new DanmakuPreparationResult
        {
            Success = false,
            FailedStage = stage,
            ErrorMessage = errorMessage,
            EpisodeMatch = match,
            Season = season,
            Episode = episode,
            XmlPath = xmlPath ?? string.Empty,
            Source = "bilibili-danmaku",
            KindSummary = "Bilibili XML -> ASS"
        };
    }
}
