using System.Text.Json;
using System.Text.Json.Serialization;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class SelectionDocumentService
{
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
        Converters = { new JsonStringEnumConverter() }
    };

    public async Task<SelectionDocument> LoadAsync(string path, CancellationToken cancellationToken = default)
    {
        var absolutePath = Path.GetFullPath(path);
        if (!File.Exists(absolutePath))
        {
            throw new FileNotFoundException("Selection 文件不存在。", absolutePath);
        }

        SelectionDocument? document;
        await using var stream = File.OpenRead(absolutePath);
        try
        {
            document = await JsonSerializer.DeserializeAsync<SelectionDocument>(stream, _jsonOptions, cancellationToken);
        }
        catch (JsonException ex)
        {
            throw new InvalidOperationException("Selection 解析失败：JSON 格式无效。", ex);
        }

        if (document is null)
        {
            throw new InvalidOperationException("Selection 解析失败。");
        }

        Validate(document);
        return document;
    }

    public async Task SaveAsync(string path, SelectionDocument document, CancellationToken cancellationToken = default)
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

    public static void Validate(SelectionDocument document)
    {
        foreach (var item in document.TargetSegments)
        {
            if (string.IsNullOrWhiteSpace(item.SegmentId))
            {
                throw new InvalidOperationException("Selection item 缺少 segmentId。");
            }
        }
    }
}
