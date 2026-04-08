using System.Text.Json;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class DanmakuExclusionRuleService
{
    private readonly JsonSerializerOptions _jsonOptions = new() { WriteIndented = true };

    public async Task ExportAsync(
        string outputPath,
        TranscodeJob job,
        IReadOnlyCollection<string> excludedCommentKeys,
        CancellationToken cancellationToken = default)
    {
        var extension = Path.GetExtension(outputPath).ToLowerInvariant();
        Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);

        if (extension == ".txt")
        {
            await File.WriteAllLinesAsync(outputPath, excludedCommentKeys.OrderBy(key => key, StringComparer.Ordinal), cancellationToken);
            return;
        }

        var document = new DanmakuExclusionRuleDocument
        {
            InputPath = job.InputPath,
            XmlPath = job.DanmakuXmlPath,
            AssPath = job.DanmakuAssPath,
            ExportedAt = DateTime.Now,
            ExcludedCommentKeys = excludedCommentKeys.OrderBy(key => key, StringComparer.Ordinal).ToList()
        };

        await using var stream = File.Create(outputPath);
        await JsonSerializer.SerializeAsync(stream, document, _jsonOptions, cancellationToken);
    }

    public async Task<HashSet<string>> ImportAsync(string inputPath, CancellationToken cancellationToken = default)
    {
        var extension = Path.GetExtension(inputPath).ToLowerInvariant();
        if (extension == ".txt")
        {
            var lines = await File.ReadAllLinesAsync(inputPath, cancellationToken);
            return lines
                .Where(line => !string.IsNullOrWhiteSpace(line))
                .Select(line => line.Trim())
                .ToHashSet(StringComparer.Ordinal);
        }

        await using var stream = File.OpenRead(inputPath);
        var document = await JsonSerializer.DeserializeAsync<DanmakuExclusionRuleDocument>(stream, _jsonOptions, cancellationToken);
        return document?.ExcludedCommentKeys?
            .Where(key => !string.IsNullOrWhiteSpace(key))
            .Select(key => key.Trim())
            .ToHashSet(StringComparer.Ordinal)
            ?? [];
    }
}
