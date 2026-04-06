using System.Text;
using System.Text.Json;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class FrameInspectionService
{
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        WriteIndented = true
    };

    public Task<InspectionReportResult> AnalyzeAsync(
        string inputPath,
        string outputDirectory,
        string source,
        IReadOnlyList<DiagnosticFrameSample> samples,
        CancellationToken cancellationToken = default)
    {
        return Task.Run(() => Analyze(inputPath, outputDirectory, source, samples, cancellationToken), cancellationToken);
    }

    public async Task ExportAsync(InspectionReportResult report, string outputPath, string format)
    {
        var extension = format.Trim().ToLowerInvariant();
        if (extension == "json")
        {
            await using var stream = File.Create(outputPath);
            await JsonSerializer.SerializeAsync(stream, report, _jsonOptions);
            return;
        }

        var builder = new StringBuilder();
        builder.AppendLine("AnimeTranscoder 巡检报告");
        builder.AppendLine($"生成时间：{report.GeneratedAt:yyyy-MM-dd HH:mm:ss}");
        builder.AppendLine($"输入文件：{report.InputPath}");
        builder.AppendLine($"截图目录：{report.OutputDirectory}");
        builder.AppendLine($"截图来源：{report.Source}");
        builder.AppendLine($"摘要：{report.Summary}");
        builder.AppendLine();

        foreach (var sample in report.Samples.OrderBy(sample => sample.TimeSeconds))
        {
            builder.AppendLine($"时间点：{sample.TimeLabel}");
            builder.AppendLine($"文件：{sample.FileName}");
            builder.AppendLine($"状态：{sample.InspectionSeverity}");
            builder.AppendLine(sample.AverageLumaLabel);
            builder.AppendLine(sample.ContrastLabel);
            builder.AppendLine($"说明：{sample.InspectionNote}");
            builder.AppendLine($"路径：{sample.OutputPath}");
            builder.AppendLine(new string('-', 72));
        }

        await File.WriteAllTextAsync(outputPath, builder.ToString(), Encoding.UTF8);
    }

    private static InspectionReportResult Analyze(
        string inputPath,
        string outputDirectory,
        string source,
        IReadOnlyList<DiagnosticFrameSample> samples,
        CancellationToken cancellationToken)
    {
        var analyzedSamples = samples
            .Select(sample =>
            {
                cancellationToken.ThrowIfCancellationRequested();
                return AnalyzeSample(sample);
            })
            .ToList();

        var attentionCount = analyzedSamples.Count(sample => sample.NeedsAttention);
        var summary = analyzedSamples.Count == 0
            ? "未找到可分析的巡检截图"
            : $"共生成 {analyzedSamples.Count} 张巡检截图，需关注 {attentionCount} 张";

        return new InspectionReportResult
        {
            GeneratedAt = DateTime.Now,
            InputPath = inputPath,
            OutputDirectory = outputDirectory,
            Source = source,
            TotalSamples = analyzedSamples.Count,
            AttentionSamples = attentionCount,
            Summary = summary,
            Samples = analyzedSamples
        };
    }

    private static DiagnosticFrameSample AnalyzeSample(DiagnosticFrameSample sample)
    {
        if (!sample.OutputExists || !File.Exists(sample.OutputPath))
        {
            return new DiagnosticFrameSample
            {
                TimeSeconds = sample.TimeSeconds,
                OutputPath = sample.OutputPath,
                OutputExists = false,
                InspectionSeverity = "缺失",
                InspectionNote = "截图文件不存在，无法进行巡检。",
                NeedsAttention = true
            };
        }

        var (averageLuma, contrastStdDev) = ReadMetrics(sample.OutputPath);
        var severity = "正常";
        var note = "亮度与对比度都在常见范围内。";
        var needsAttention = false;

        if (averageLuma < 40)
        {
            severity = "偏暗";
            note = "画面整体偏暗，可能存在黑场或压制偏暗。";
            needsAttention = true;
        }
        else if (averageLuma > 215)
        {
            severity = "偏亮";
            note = "画面整体偏亮，可能存在过曝或高亮异常。";
            needsAttention = true;
        }

        if (contrastStdDev < 18)
        {
            if (needsAttention)
            {
                severity = "需关注";
                note = $"{note} 同时对比度偏低，画面可能发灰。";
            }
            else
            {
                severity = "低对比度";
                note = "画面对比度偏低，细节层次可能不足。";
                needsAttention = true;
            }
        }

        return new DiagnosticFrameSample
        {
            TimeSeconds = sample.TimeSeconds,
            OutputPath = sample.OutputPath,
            OutputExists = sample.OutputExists,
            AverageLuma = averageLuma,
            ContrastStdDev = contrastStdDev,
            InspectionSeverity = severity,
            InspectionNote = note,
            NeedsAttention = needsAttention
        };
    }

    private static (double averageLuma, double contrastStdDev) ReadMetrics(string imagePath)
    {
        using var stream = File.OpenRead(imagePath);
        var decoder = BitmapDecoder.Create(stream, BitmapCreateOptions.IgnoreColorProfile, BitmapCacheOption.OnLoad);
        var frame = decoder.Frames[0];

        BitmapSource source = frame.Format == PixelFormats.Bgra32
            ? frame
            : new FormatConvertedBitmap(frame, PixelFormats.Bgra32, null, 0);

        var stride = source.PixelWidth * 4;
        var pixels = new byte[stride * source.PixelHeight];
        source.CopyPixels(pixels, stride, 0);

        var pixelCount = source.PixelWidth * source.PixelHeight;
        var step = Math.Max(1, pixelCount / 12000);
        double sum = 0;
        double sumSquares = 0;
        var count = 0;

        for (var pixelIndex = 0; pixelIndex < pixelCount; pixelIndex += step)
        {
            var offset = pixelIndex * 4;
            var blue = pixels[offset];
            var green = pixels[offset + 1];
            var red = pixels[offset + 2];
            var luma = 0.0722 * blue + 0.7152 * green + 0.2126 * red;
            sum += luma;
            sumSquares += luma * luma;
            count++;
        }

        if (count == 0)
        {
            return (0, 0);
        }

        var average = sum / count;
        var variance = Math.Max(0, (sumSquares / count) - (average * average));
        var stdDev = Math.Sqrt(variance);
        return (average, stdDev);
    }
}
