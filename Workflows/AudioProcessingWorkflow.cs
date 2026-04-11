using AnimeTranscoder.Models;
using AnimeTranscoder.Services;

namespace AnimeTranscoder.Workflows;

public sealed class AudioProcessingWorkflow
{
    private readonly AudioExtractionService _audioExtractionService;

    public AudioProcessingWorkflow(AudioExtractionService audioExtractionService)
    {
        _audioExtractionService = audioExtractionService;
    }

    public async Task<AudioExtractionResult> ExtractAsync(
        string inputPath,
        string outputPath,
        AudioFormat format,
        int? trackIndex,
        TimeSpan? startTime,
        TimeSpan? duration,
        bool normalize,
        int bitrateKbps,
        double totalDurationSeconds,
        IProgress<WorkflowProgress>? progress,
        CancellationToken cancellationToken)
    {
        var result = await _audioExtractionService.ExtractAsync(
            inputPath,
            outputPath,
            format,
            trackIndex,
            startTime,
            duration,
            normalize,
            bitrateKbps,
            totalDurationSeconds,
            (progressValue, speed) => ReportProgress(progress, "audio.extract", progressValue, speed, "正在提取音频"),
            cancellationToken);

        if (result.Success)
        {
            ReportProgress(progress, "audio.extract", 100d, "done", "音频提取完成");
        }

        return result;
    }

    public async Task<IReadOnlyList<SilenceSegment>> DetectSilenceAsync(
        string inputPath,
        int? trackIndex,
        double noiseThresholdDb,
        double minimumDurationSeconds,
        IProgress<WorkflowProgress>? progress,
        CancellationToken cancellationToken)
    {
        ReportProgress(progress, "audio.detect-silence", 0d, string.Empty, "正在分析静音区间");
        var result = await _audioExtractionService.DetectSilenceAsync(
            inputPath,
            trackIndex,
            noiseThresholdDb,
            minimumDurationSeconds,
            cancellationToken);
        ReportProgress(progress, "audio.detect-silence", 100d, "done", "静音检测完成");
        return result;
    }

    private static void ReportProgress(
        IProgress<WorkflowProgress>? progress,
        string stage,
        double progressValue,
        string speed,
        string message)
    {
        progress?.Report(new WorkflowProgress
        {
            Stage = stage,
            ProgressPercent = progressValue,
            Speed = speed,
            Message = message,
            Timestamp = DateTimeOffset.UtcNow
        });
    }
}
