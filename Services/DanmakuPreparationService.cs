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
        TranscodeJob job,
        AppSettings settings,
        Action<string>? logCallback,
        CancellationToken cancellationToken = default)
    {
        var excludedCommentKeys = ParseExcludedCommentKeys(job);

        if (!settings.EnableDanmaku)
        {
            return new DanmakuPreparationResult
            {
                Success = true,
                Source = "danmaku-disabled",
                KindSummary = "弹幕已禁用",
                Summary = "当前任务未启用弹幕"
            };
        }

        if (string.Equals(settings.DanmakuSourceMode, DanmakuSourceModes.LocalFile, StringComparison.OrdinalIgnoreCase))
        {
            return await PrepareFromLocalFileAsync(job, settings, logCallback, cancellationToken);
        }

        AnimeEpisodeMatch? match = null;
        BangumiSeasonInfo? season = null;
        BangumiEpisodeInfo? episode = null;
        string? xmlPath = null;
        var xmlCommentCount = 0;

        try
        {
            match = _parserService.Parse(job.InputPath);
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
                excludedCommentKeys,
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

    private async Task<DanmakuPreparationResult> PrepareFromLocalFileAsync(
        TranscodeJob job,
        AppSettings settings,
        Action<string>? logCallback,
        CancellationToken cancellationToken)
    {
        var excludedCommentKeys = ParseExcludedCommentKeys(job);

        if (string.IsNullOrWhiteSpace(job.DanmakuInputPath))
        {
            return new DanmakuPreparationResult
            {
                Success = false,
                FailedStage = "本地弹幕导入",
                ErrorMessage = "当前任务还没有绑定本地弹幕文件。",
                Source = "local-danmaku",
                KindSummary = "本地弹幕"
            };
        }

        if (!File.Exists(job.DanmakuInputPath))
        {
            return new DanmakuPreparationResult
            {
                Success = false,
                FailedStage = "本地弹幕导入",
                ErrorMessage = $"弹幕文件不存在：{job.DanmakuInputPath}",
                Source = "local-danmaku",
                KindSummary = "本地弹幕"
            };
        }

        var extension = Path.GetExtension(job.DanmakuInputPath);
        if (string.Equals(extension, ".ass", StringComparison.OrdinalIgnoreCase))
        {
            logCallback?.Invoke($"已加载本地 ASS：{job.DanmakuInputPath}");
            return new DanmakuPreparationResult
            {
                Success = true,
                AssPath = job.DanmakuInputPath,
                Source = "local-ass",
                KindSummary = $"本地 ASS | {Path.GetFileName(job.DanmakuInputPath)}",
                Summary = $"已直接使用本地 ASS：{Path.GetFileName(job.DanmakuInputPath)}"
            };
        }

        if (!string.Equals(extension, ".xml", StringComparison.OrdinalIgnoreCase))
        {
            return new DanmakuPreparationResult
            {
                Success = false,
                FailedStage = "本地弹幕导入",
                ErrorMessage = "当前仅支持导入 XML 或 ASS 弹幕文件。",
                Source = "local-danmaku",
                KindSummary = "本地弹幕"
            };
        }

        try
        {
            var (assPath, xmlCommentCount, assCommentCount) = await _assGeneratorService.GenerateFromXmlAsync(
                $"local|{job.InputPath}|{job.DanmakuInputPath}",
                job.DanmakuInputPath,
                settings,
                excludedCommentKeys,
                logCallback,
                cancellationToken);

            return new DanmakuPreparationResult
            {
                Success = true,
                XmlPath = job.DanmakuInputPath,
                AssPath = assPath,
                XmlCommentCount = xmlCommentCount,
                AssCommentCount = assCommentCount,
                Source = "local-xml",
                KindSummary = $"本地 XML {xmlCommentCount} 条 -> ASS {assCommentCount} 条",
                Summary = $"{Path.GetFileName(job.DanmakuInputPath)} | XML {xmlCommentCount} 条 | ASS {assCommentCount} 条"
            };
        }
        catch (Exception ex)
        {
            return new DanmakuPreparationResult
            {
                Success = false,
                FailedStage = "ASS 生成",
                ErrorMessage = ex.Message,
                XmlPath = job.DanmakuInputPath,
                Source = "local-xml",
                KindSummary = "本地 XML -> ASS"
            };
        }
    }

    private static IReadOnlySet<string> ParseExcludedCommentKeys(TranscodeJob job)
    {
        return job.DanmakuExcludedCommentKeys
            .Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .ToHashSet(StringComparer.Ordinal);
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
