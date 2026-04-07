using System.Net;
using System.Net.Http;
using System.Xml.Linq;
using AnimeTranscoder.Infrastructure;

namespace AnimeTranscoder.Services;

public sealed class DanmakuXmlService
{
    private readonly DanmakuCacheService _cacheService;
    private readonly HttpClient _httpClient;

    public DanmakuXmlService(DanmakuCacheService cacheService)
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

    public async Task<(string XmlPath, int CommentCount)> DownloadAsync(long cid, Action<string>? logCallback, CancellationToken cancellationToken = default)
    {
        var cacheKey = cid.ToString();
        var xml = await _cacheService.GetOrCreateTextAsync(
            "bilibili-xml",
            cacheKey,
            "xml",
            async token =>
            {
                using var request = new HttpRequestMessage(HttpMethod.Get, $"https://comment.bilibili.com/{cid}.xml");
                request.Headers.TryAddWithoutValidation("User-Agent", "Mozilla/5.0");
                request.Headers.Referrer = new Uri("https://www.bilibili.com/");

                using var response = await _httpClient.SendAsync(request, token);
                var payload = await response.Content.ReadAsStringAsync(token);
                if (!response.IsSuccessStatusCode)
                {
                    AppFileLogger.Write("DanmakuXmlService", $"XML 下载失败：cid={cid} status={response.StatusCode}");
                    throw new InvalidOperationException($"XML 下载失败：{response.StatusCode}");
                }

                if (string.IsNullOrWhiteSpace(payload))
                {
                    throw new InvalidOperationException($"XML 下载返回空内容：cid={cid}");
                }

                return payload;
            },
            cancellationToken);

        var commentCount = CountComments(xml);
        var xmlPath = _cacheService.GetCachePath("bilibili-xml", cacheKey, "xml");
        logCallback?.Invoke($"XML 下载完成：cid={cid} | 评论数 {commentCount} | {xmlPath}");
        return (xmlPath, commentCount);
    }

    private static int CountComments(string xml)
    {
        try
        {
            var document = XDocument.Parse(xml);
            return document.Descendants("d").Count();
        }
        catch
        {
            return 0;
        }
    }
}
