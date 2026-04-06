namespace AnimeTranscoder.Models;

public sealed class DiagnosticFrameSample
{
    public double TimeSeconds { get; init; }
    public string OutputPath { get; init; } = string.Empty;
    public bool OutputExists { get; init; }
    public double AverageLuma { get; init; }
    public double ContrastStdDev { get; init; }
    public string InspectionSeverity { get; init; } = "未分析";
    public string InspectionNote { get; init; } = string.Empty;
    public bool NeedsAttention { get; init; }

    public string TimeLabel => $"{TimeSeconds:0.000}s";

    public string FileName => string.IsNullOrWhiteSpace(OutputPath)
        ? "未生成"
        : Path.GetFileName(OutputPath);

    public string AverageLumaLabel => AverageLuma <= 0
        ? "亮度：未分析"
        : $"亮度：{AverageLuma:0.0}";

    public string ContrastLabel => ContrastStdDev <= 0
        ? "对比度：未分析"
        : $"对比度：{ContrastStdDev:0.0}";
}
