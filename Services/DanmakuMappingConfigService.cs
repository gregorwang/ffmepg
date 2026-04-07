using System.Text.Json;
using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class DanmakuMappingConfigService
{
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true
    };

    public async Task<DanmakuMappingConfig> LoadAsync(string mappingPath, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(mappingPath))
        {
            return new DanmakuMappingConfig();
        }

        var directory = Path.GetDirectoryName(mappingPath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        if (!File.Exists(mappingPath))
        {
            await using var createStream = File.Create(mappingPath);
            await JsonSerializer.SerializeAsync(createStream, new DanmakuMappingConfig(), _jsonOptions, cancellationToken);
            AppFileLogger.Write("DanmakuMappingConfigService", $"已创建默认番剧映射文件：{mappingPath}");
            return new DanmakuMappingConfig();
        }

        await using var stream = File.OpenRead(mappingPath);
        var config = await JsonSerializer.DeserializeAsync<DanmakuMappingConfig>(stream, _jsonOptions, cancellationToken);
        return config ?? new DanmakuMappingConfig();
    }

    public DanmakuTitleMappingEntry? FindBestMatch(AnimeEpisodeMatch match, DanmakuMappingConfig config)
    {
        return config.Mappings
            .Select(entry => new { Entry = entry, Score = ScoreEntry(match, entry) })
            .Where(item => item.Score > 0)
            .OrderByDescending(item => item.Score)
            .Select(item => item.Entry)
            .FirstOrDefault();
    }

    private static int ScoreEntry(AnimeEpisodeMatch match, DanmakuTitleMappingEntry entry)
    {
        var bestScore = 0;
        foreach (var localTitle in entry.LocalTitles.Append(entry.Name))
        {
            var normalized = AnimeEpisodeParserService.NormalizeForMatch(localTitle);
            if (string.IsNullOrWhiteSpace(normalized))
            {
                continue;
            }

            if (string.Equals(normalized, match.NormalizedTitle, StringComparison.Ordinal))
            {
                bestScore = Math.Max(bestScore, 300);
                continue;
            }

            if (match.NormalizedTitle.Contains(normalized, StringComparison.Ordinal) ||
                normalized.Contains(match.NormalizedTitle, StringComparison.Ordinal))
            {
                bestScore = Math.Max(bestScore, 180);
            }
        }

        if (!string.IsNullOrWhiteSpace(entry.SearchKeyword))
        {
            var normalizedKeyword = AnimeEpisodeParserService.NormalizeForMatch(entry.SearchKeyword);
            if (string.Equals(normalizedKeyword, match.NormalizedTitle, StringComparison.Ordinal))
            {
                bestScore = Math.Max(bestScore, 220);
            }
        }

        return bestScore;
    }
}
