using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class TaskHistoryService
{
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        WriteIndented = true,
        Converters = { new JsonStringEnumConverter() }
    };

    public string HistoryPath { get; }

    public TaskHistoryService()
    {
        var appDirectory = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "AnimeTranscoder");

        Directory.CreateDirectory(appDirectory);
        HistoryPath = Path.Combine(appDirectory, "history.json");
    }

    public async Task<IReadOnlyList<TaskHistoryEntry>> LoadAsync()
    {
        if (!File.Exists(HistoryPath))
        {
            return [];
        }

        await using var stream = File.OpenRead(HistoryPath);
        var entries = await JsonSerializer.DeserializeAsync<List<TaskHistoryEntry>>(stream, _jsonOptions);
        return entries ?? [];
    }

    public async Task SaveAsync(IEnumerable<TaskHistoryEntry> entries)
    {
        await using var stream = File.Create(HistoryPath);
        await JsonSerializer.SerializeAsync(stream, entries, _jsonOptions);
    }

    public async Task ExportAsync(IEnumerable<TaskHistoryEntry> entries, string outputPath, string format)
    {
        var materialized = entries.ToList();
        var extension = format.Trim().ToLowerInvariant();

        if (extension == "json")
        {
            await using var stream = File.Create(outputPath);
            await JsonSerializer.SerializeAsync(stream, materialized, _jsonOptions);
            return;
        }

        var builder = new StringBuilder();
        builder.AppendLine("AnimeTranscoder 任务历史导出");
        builder.AppendLine($"导出时间：{DateTime.Now:yyyy-MM-dd HH:mm:ss}");
        builder.AppendLine($"任务数量：{materialized.Count}");
        builder.AppendLine();

        foreach (var entry in materialized.OrderByDescending(item => item.RecordedAt))
        {
            builder.AppendLine($"时间：{entry.RecordedAt:yyyy-MM-dd HH:mm:ss}");
            builder.AppendLine($"文件：{entry.FileName}");
            builder.AppendLine($"状态：{entry.StatusText}");
            builder.AppendLine($"说明：{entry.Message}");
            builder.AppendLine($"编码器：{entry.EncoderUsed}");
            builder.AppendLine($"字幕序号：{entry.SubtitleStreamOrdinal?.ToString() ?? "无"}");
            builder.AppendLine($"字幕分析：{entry.SubtitleAnalysisSource}");
            builder.AppendLine($"字幕类型：{entry.SubtitleKindSummary}");
            builder.AppendLine($"输入：{entry.InputPath}");
            builder.AppendLine($"输出：{entry.OutputPath}");
            builder.AppendLine(new string('-', 72));
        }

        await File.WriteAllTextAsync(outputPath, builder.ToString(), Encoding.UTF8);
    }
}
