using System.Net;
using System.Net.Http;
using System.Text.Json;
using System.Text.RegularExpressions;
using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class BilibiliBangumiClient
{
    private readonly DanmakuCacheService _cacheService;
    private readonly HttpClient _httpClient;

    public BilibiliBangumiClient(DanmakuCacheService cacheService)
    {
        _cacheService = cacheService;
        _httpClient = new HttpClient(new HttpClientHandler
        {
            AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate | DecompressionMethods.Brotli
        })
        {
            Timeout = TimeSpan.FromSeconds(15)
        };
    }

    public async Task<IReadOnlyList<BangumiSeasonInfo>> SearchSeasonsAsync(string keyword, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(keyword))
        {
            return [];
        }

        var normalizedKeyword = keyword.Trim();
        return await _cacheService.GetOrCreateJsonAsync(
            "bilibili-search",
            normalizedKeyword,
            async token =>
            {
                var uri = $"https://api.bilibili.com/x/web-interface/search/type?search_type=media_bangumi&keyword={Uri.EscapeDataString(normalizedKeyword)}";
                var json = await GetStringAsync(uri, "BilibiliBangumiClient.Search", token);
                return ParseSearchResults(json);
            },
            cancellationToken);
    }

    public async Task<BangumiSeasonInfo> GetSeasonDetailAsync(int seasonId, CancellationToken cancellationToken = default)
    {
        return await _cacheService.GetOrCreateJsonAsync(
            "bilibili-season",
            seasonId.ToString(),
            async token =>
            {
                var uri = $"https://api.bilibili.com/pgc/view/web/season?season_id={seasonId}";
                var json = await GetStringAsync(uri, "BilibiliBangumiClient.Season", token);
                return ParseSeasonDetail(json, seasonId);
            },
            cancellationToken);
    }

    private async Task<string> GetStringAsync(string uri, string source, CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, uri);
        request.Headers.TryAddWithoutValidation("User-Agent", "Mozilla/5.0");
        request.Headers.Referrer = new Uri("https://www.bilibili.com/");

        using var response = await _httpClient.SendAsync(request, cancellationToken);
        var payload = await response.Content.ReadAsStringAsync(cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            AppFileLogger.Write(source, $"请求失败：{response.StatusCode} | {uri}");
            throw new InvalidOperationException($"Bilibili 接口请求失败：{response.StatusCode}");
        }

        if (string.IsNullOrWhiteSpace(payload))
        {
            AppFileLogger.Write(source, $"请求成功但响应为空：{uri}");
            throw new InvalidOperationException("Bilibili 接口返回空响应。");
        }

        return payload;
    }

    private static List<BangumiSeasonInfo> ParseSearchResults(string json)
    {
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;
        var code = root.TryGetProperty("code", out var codeElement) ? codeElement.GetInt32() : -1;
        if (code != 0)
        {
            var message = root.TryGetProperty("message", out var messageElement)
                ? messageElement.GetString() ?? "unknown"
                : "unknown";
            throw new InvalidOperationException($"Bilibili 番剧搜索失败：{message}");
        }

        if (!root.TryGetProperty("data", out var data) ||
            !data.TryGetProperty("result", out var resultArray))
        {
            return [];
        }

        var results = new List<BangumiSeasonInfo>();
        foreach (var item in resultArray.EnumerateArray())
        {
            var seasonId = ReadInt(item, "season_id");
            if (seasonId <= 0)
            {
                seasonId = ReadInt(item, "pgc_season_id");
            }

            if (seasonId <= 0)
            {
                continue;
            }

            results.Add(new BangumiSeasonInfo
            {
                SeasonId = seasonId,
                Title = StripHtml(ReadString(item, "title")),
                OriginalTitle = StripHtml(ReadString(item, "org_title")),
                Url = ReadString(item, "url"),
                SeasonTypeName = ReadString(item, "season_type_name"),
                EpisodeCount = ReadInt(item, "ep_size")
            });
        }

        return results;
    }

    private static BangumiSeasonInfo ParseSeasonDetail(string json, int expectedSeasonId)
    {
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;
        var code = root.TryGetProperty("code", out var codeElement) ? codeElement.GetInt32() : -1;
        if (code != 0)
        {
            var message = root.TryGetProperty("message", out var messageElement)
                ? messageElement.GetString() ?? "unknown"
                : "unknown";
            throw new InvalidOperationException($"Bilibili 番剧详情获取失败：{message}");
        }

        var result = root.GetProperty("result");
        var seasonTitle = ReadString(result, "title");
        var originalTitle = ReadString(result, "jp_title");
        var series = result.TryGetProperty("series", out var seriesElement)
            ? ReadString(seriesElement, "series_title")
            : string.Empty;
        var shareUrl = ReadString(result, "share_url");

        var episodes = new List<BangumiEpisodeInfo>();
        if (result.TryGetProperty("episodes", out var episodesElement))
        {
            foreach (var episode in episodesElement.EnumerateArray())
            {
                var title = ReadString(episode, "title");
                var showTitle = ReadString(episode, "show_title");
                var shareCopy = ReadString(episode, "share_copy");

                episodes.Add(new BangumiEpisodeInfo
                {
                    EpisodeId = ReadInt(episode, "ep_id", ReadInt(episode, "id")),
                    Cid = ReadLong(episode, "cid"),
                    Number = ResolveEpisodeNumber(title, showTitle, shareCopy),
                    Title = title,
                    LongTitle = ReadString(episode, "long_title"),
                    ShowTitle = showTitle,
                    ShareCopy = shareCopy,
                    SectionType = ReadInt(episode, "section_type")
                });
            }
        }

        return new BangumiSeasonInfo
        {
            SeasonId = ReadInt(result, "season_id", expectedSeasonId),
            Title = seasonTitle,
            OriginalTitle = originalTitle,
            SeriesTitle = string.IsNullOrWhiteSpace(series) ? seasonTitle : series,
            Url = shareUrl,
            EpisodeCount = ReadInt(result, "total", episodes.Count),
            Episodes = episodes
        };
    }

    private static int ResolveEpisodeNumber(string title, string showTitle, string shareCopy)
    {
        if (int.TryParse(title, out var directValue))
        {
            return directValue;
        }

        foreach (var candidate in new[] { showTitle, shareCopy })
        {
            var match = Regex.Match(candidate, @"第\s*(?<episode>\d{1,3})\s*[话話集]");
            if (match.Success && int.TryParse(match.Groups["episode"].Value, out var episodeNumber))
            {
                return episodeNumber;
            }

            match = Regex.Match(candidate, @"\b(?<episode>\d{1,3})\b");
            if (match.Success && int.TryParse(match.Groups["episode"].Value, out episodeNumber))
            {
                return episodeNumber;
            }
        }

        return 0;
    }

    private static string ReadString(JsonElement element, string name)
    {
        return element.TryGetProperty(name, out var value)
            ? value.GetString() ?? string.Empty
            : string.Empty;
    }

    private static int ReadInt(JsonElement element, string name, int fallback = 0)
    {
        if (!element.TryGetProperty(name, out var value))
        {
            return fallback;
        }

        return value.ValueKind switch
        {
            JsonValueKind.Number => value.GetInt32(),
            JsonValueKind.String when int.TryParse(value.GetString(), out var parsed) => parsed,
            _ => fallback
        };
    }

    private static long ReadLong(JsonElement element, string name)
    {
        if (!element.TryGetProperty(name, out var value))
        {
            return 0;
        }

        return value.ValueKind switch
        {
            JsonValueKind.Number => value.GetInt64(),
            JsonValueKind.String when long.TryParse(value.GetString(), out var parsed) => parsed,
            _ => 0
        };
    }

    private static string StripHtml(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        return Regex.Replace(WebUtility.HtmlDecode(value), "<.*?>", string.Empty).Trim();
    }
}
