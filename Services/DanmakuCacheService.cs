using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace AnimeTranscoder.Services;

public sealed class DanmakuCacheService
{
    private static readonly TimeSpan CacheTtl = TimeSpan.FromDays(14);
    private readonly ConcurrentDictionary<string, object> _memoryCache = new();
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true
    };

    public DanmakuCacheService()
    {
        CacheRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "AnimeTranscoder",
            "cache",
            "danmaku");

        Directory.CreateDirectory(CacheRoot);
    }

    public string CacheRoot { get; }

    public string GetCachePath(string bucket, string cacheKey, string extension)
    {
        var bucketDirectory = Path.Combine(CacheRoot, bucket);
        Directory.CreateDirectory(bucketDirectory);
        return Path.Combine(bucketDirectory, $"{ComputeHash(cacheKey)}.{extension.TrimStart('.')}");
    }

    public async Task<T> GetOrCreateJsonAsync<T>(
        string bucket,
        string cacheKey,
        Func<CancellationToken, Task<T>> factory,
        CancellationToken cancellationToken = default)
    {
        var path = GetCachePath(bucket, cacheKey, "json");
        var memoryKey = $"{bucket}|json|{cacheKey}";

        if (_memoryCache.TryGetValue(memoryKey, out var cachedValue) &&
            cachedValue is T typedValue)
        {
            return typedValue;
        }

        if (File.Exists(path) && IsFresh(path))
        {
            var json = await File.ReadAllTextAsync(path, cancellationToken);
            var deserialized = JsonSerializer.Deserialize<T>(json, _jsonOptions);
            if (deserialized is not null)
            {
                _memoryCache[memoryKey] = deserialized;
                return deserialized;
            }
        }

        var value = await factory(cancellationToken);
        var serialized = JsonSerializer.Serialize(value, _jsonOptions);
        await File.WriteAllTextAsync(path, serialized, Encoding.UTF8, cancellationToken);
        _memoryCache[memoryKey] = value!;
        return value;
    }

    public async Task<string> GetOrCreateTextAsync(
        string bucket,
        string cacheKey,
        string extension,
        Func<CancellationToken, Task<string>> factory,
        CancellationToken cancellationToken = default)
    {
        var path = GetCachePath(bucket, cacheKey, extension);
        var memoryKey = $"{bucket}|{extension}|{cacheKey}";

        if (_memoryCache.TryGetValue(memoryKey, out var cachedValue) &&
            cachedValue is string cachedText)
        {
            return cachedText;
        }

        if (File.Exists(path) && IsFresh(path))
        {
            var existingText = await File.ReadAllTextAsync(path, cancellationToken);
            _memoryCache[memoryKey] = existingText;
            return existingText;
        }

        var text = await factory(cancellationToken);
        await File.WriteAllTextAsync(path, text, Encoding.UTF8, cancellationToken);
        _memoryCache[memoryKey] = text;
        return text;
    }

    private static bool IsFresh(string path)
    {
        return DateTime.UtcNow - File.GetLastWriteTimeUtc(path) <= CacheTtl;
    }

    private static string ComputeHash(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }
}
