using System.Text.Json;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class TranscriptDocumentService
{
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    };

    public async Task<TranscriptDocument> LoadAsync(string path, CancellationToken cancellationToken = default)
    {
        var absolutePath = Path.GetFullPath(path);
        if (!File.Exists(absolutePath))
        {
            throw new FileNotFoundException("Transcript 文件不存在。", absolutePath);
        }

        TranscriptDocument? document;
        await using var stream = File.OpenRead(absolutePath);
        try
        {
            document = await JsonSerializer.DeserializeAsync<TranscriptDocument>(stream, _jsonOptions, cancellationToken);
        }
        catch (JsonException ex)
        {
            throw new InvalidOperationException("Transcript 解析失败：JSON 格式无效。", ex);
        }

        if (document is null)
        {
            throw new InvalidOperationException("Transcript 解析失败。");
        }

        Validate(document);
        return document;
    }

    public async Task SaveAsync(string path, TranscriptDocument document, CancellationToken cancellationToken = default)
    {
        Validate(document);

        var absolutePath = Path.GetFullPath(path);
        var directory = Path.GetDirectoryName(absolutePath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        await using var stream = File.Create(absolutePath);
        await JsonSerializer.SerializeAsync(stream, document, _jsonOptions, cancellationToken);
    }

    public static void Validate(TranscriptDocument document)
    {
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var segment in document.Segments)
        {
            if (string.IsNullOrWhiteSpace(segment.Id))
            {
                throw new InvalidOperationException("Transcript segment 缺少 id。");
            }

            if (!ids.Add(segment.Id))
            {
                throw new InvalidOperationException($"Transcript segment id 重复：{segment.Id}");
            }

            if (segment.End < segment.Start)
            {
                throw new InvalidOperationException($"Transcript segment 时间区间无效：{segment.Id}");
            }
        }
    }
}
