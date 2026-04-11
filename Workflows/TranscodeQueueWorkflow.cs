using AnimeTranscoder.Models;
using AnimeTranscoder.Services;

namespace AnimeTranscoder.Workflows;

public sealed class TranscodeQueueWorkflow
{
    private const int OutputValidationToleranceSeconds = 5;
    private readonly Func<string, string, int, CancellationToken, Task<OutputValidationResult>> _validateOutputAsync;
    private readonly Func<string, string, AppSettings, StoragePreflightResult> _validateOutputPath;
    private readonly Func<string, CancellationToken, Task<MediaProbeResult?>> _probeMediaAsync;
    private readonly Func<string, bool, string> _resolveVideoEncoder;
    private readonly Func<TranscodeTaskSpec, MediaProbeResult, TranscodeOverlayPreparationResult, AppSettings, string, Action<double, string>?, Action<string>?, CancellationToken, Task<TranscodeResult>> _runTranscodeAsync;

    public TranscodeQueueWorkflow(
        OutputValidationService outputValidationService,
        StoragePreflightService storagePreflightService,
        NativeMediaCoreService nativeMediaCoreService,
        FfprobeService ffprobeService,
        HardwareDetectionService hardwareDetectionService,
        DanmakuBurnCommandBuilder danmakuBurnCommandBuilder,
        FfmpegRunner ffmpegRunner)
        : this(
            (inputPath, outputPath, toleranceSeconds, cancellationToken) =>
                outputValidationService.ValidateAsync(inputPath, outputPath, toleranceSeconds, cancellationToken),
            storagePreflightService.ValidateOutputPath,
            async (inputPath, cancellationToken) =>
                await nativeMediaCoreService.ProbeMediaAsync(inputPath, cancellationToken)
                ?? await ffprobeService.ProbeAsync(inputPath, cancellationToken),
            hardwareDetectionService.ResolveVideoEncoder,
            async (task, probe, overlay, settings, videoEncoder, progressCallback, logCallback, cancellationToken) =>
            {
                Directory.CreateDirectory(Path.GetDirectoryName(task.OutputPath) ?? AppContext.BaseDirectory);
                var arguments = danmakuBurnCommandBuilder.BuildArguments(
                    task.InputPath,
                    task.OutputPath,
                    overlay.DanmakuAssPath,
                    overlay.SubtitleStreamOrdinal,
                    settings,
                    videoEncoder);

                return await ffmpegRunner.RunAsync(
                    arguments,
                    probe.Duration.TotalSeconds,
                    progressCallback,
                    logCallback,
                    cancellationToken);
            })
    {
    }

    public TranscodeQueueWorkflow(
        Func<string, string, int, CancellationToken, Task<OutputValidationResult>> validateOutputAsync,
        Func<string, string, AppSettings, StoragePreflightResult> validateOutputPath,
        Func<string, CancellationToken, Task<MediaProbeResult?>> probeMediaAsync,
        Func<string, bool, string> resolveVideoEncoder,
        Func<TranscodeTaskSpec, MediaProbeResult, TranscodeOverlayPreparationResult, AppSettings, string, Action<double, string>?, Action<string>?, CancellationToken, Task<TranscodeResult>> runTranscodeAsync)
    {
        _validateOutputAsync = validateOutputAsync;
        _validateOutputPath = validateOutputPath;
        _probeMediaAsync = probeMediaAsync;
        _resolveVideoEncoder = resolveVideoEncoder;
        _runTranscodeAsync = runTranscodeAsync;
    }

    public async Task<TranscodeQueueExecutionResult> ExecuteAsync(
        IReadOnlyList<TranscodeTaskSpec> tasks,
        AppSettings settings,
        bool isNvencAvailable,
        Func<TranscodeTaskSpec, MediaProbeResult, Action<string>?, CancellationToken, Task<TranscodeOverlayPreparationResult>> prepareOverlayAsync,
        Func<TranscodeTaskResult, Task>? onTaskCompletedAsync,
        IProgress<WorkflowProgress>? progress,
        Action<string>? logCallback,
        CancellationToken cancellationToken)
    {
        var results = new List<TranscodeTaskResult>(tasks.Count);
        var queueWasCancelled = false;

        foreach (var task in tasks)
        {
            if (cancellationToken.IsCancellationRequested)
            {
                queueWasCancelled = true;
                break;
            }

            var taskResult = CreateTaskResult(task);
            ReportProgress(progress, task, "queue.probing", 0d, string.Empty, "正在读取媒体信息");

            if (!File.Exists(task.InputPath))
            {
                taskResult.Status = JobStatus.Failed;
                taskResult.Message = "找不到输入文件";
                await CompleteTaskAsync(results, taskResult, onTaskCompletedAsync);
                continue;
            }

            if (!settings.OverwriteExisting)
            {
                var skipValidation = await _validateOutputAsync(
                    task.InputPath,
                    task.OutputPath,
                    OutputValidationToleranceSeconds,
                    cancellationToken);
                logCallback?.Invoke($"输出校验：{skipValidation.Source} | 差值 {skipValidation.DifferenceSeconds:0.000}s | {skipValidation.Message}");

                if (skipValidation.IsMatch)
                {
                    taskResult.Status = JobStatus.Skipped;
                    taskResult.ProgressPercent = 100d;
                    taskResult.Message = "已存在有效输出文件";
                    ReportProgress(progress, task, "queue.skipped", 100d, "done", taskResult.Message);
                    logCallback?.Invoke($"已跳过 {task.FileName}：目标文件已存在且校验通过。");
                    await CompleteTaskAsync(results, taskResult, onTaskCompletedAsync);
                    continue;
                }
            }

            var storagePreflight = _validateOutputPath(task.InputPath, task.OutputPath, settings);
            logCallback?.Invoke(storagePreflight.Message);
            if (!storagePreflight.HasEnoughSpace)
            {
                taskResult.Status = JobStatus.Failed;
                taskResult.Message = "输出目录空间不足";
                ReportProgress(progress, task, "queue.failed", 0d, string.Empty, taskResult.Message);
                await CompleteTaskAsync(results, taskResult, onTaskCompletedAsync);
                continue;
            }

            var probe = await _probeMediaAsync(task.InputPath, cancellationToken);
            if (probe is null)
            {
                taskResult.Status = JobStatus.Failed;
                taskResult.Message = "媒体分析失败";
                ReportProgress(progress, task, "queue.failed", 0d, string.Empty, taskResult.Message);
                await CompleteTaskAsync(results, taskResult, onTaskCompletedAsync);
                continue;
            }

            taskResult.SourceDurationSeconds = probe.Duration.TotalSeconds;
            logCallback?.Invoke(probe.Message);

            var videoEncoder = _resolveVideoEncoder(settings.VideoEncoderMode, isNvencAvailable);
            taskResult.EncoderUsed = videoEncoder;
            ReportProgress(progress, task, "queue.prepare-overlay", 0d, string.Empty, "正在准备叠加素材");

            var overlay = await prepareOverlayAsync(task, probe, logCallback, cancellationToken);
            if (!overlay.Success)
            {
                taskResult.Status = JobStatus.Failed;
                taskResult.Message = overlay.ErrorMessage;
                ApplyOverlayResult(taskResult, overlay);
                ReportProgress(progress, task, "queue.failed", 0d, string.Empty, taskResult.Message);
                logCallback?.Invoke($"处理失败 {task.FileName}：{overlay.ErrorMessage}");
                await CompleteTaskAsync(results, taskResult, onTaskCompletedAsync);
                continue;
            }

            ApplyOverlayResult(taskResult, overlay);
            var modeSummary = BuildOverlayModeSummary(overlay.SubtitleStreamOrdinal, overlay.DanmakuAssPath);
            logCallback?.Invoke(
                $"开始处理 {task.FileName}，编码器：{videoEncoder}，模式：{modeSummary}，" +
                $"音频策略：{(settings.PreferStereoAudio ? "AAC 立体声" : "AAC 多声道")}，faststart：{(settings.EnableFaststart ? "开启" : "关闭")}。");

            var transcodeResult = await _runTranscodeAsync(
                task,
                probe,
                overlay,
                settings,
                videoEncoder,
                (progressValue, speed) =>
                {
                    taskResult.ProgressPercent = Math.Round(progressValue, 2);
                    if (!string.IsNullOrWhiteSpace(speed) &&
                        !string.Equals(speed, "done", StringComparison.OrdinalIgnoreCase))
                    {
                        taskResult.Speed = speed;
                    }

                    ReportProgress(progress, task, "queue.transcoding", progressValue, speed, $"正在烧录{modeSummary}");
                },
                logCallback,
                cancellationToken);

            if (cancellationToken.IsCancellationRequested)
            {
                queueWasCancelled = true;
                taskResult.Status = JobStatus.Cancelled;
                taskResult.Message = "任务已取消";
                ReportProgress(progress, task, "queue.cancelled", taskResult.ProgressPercent, taskResult.Speed, taskResult.Message);
                await CompleteTaskAsync(results, taskResult, onTaskCompletedAsync);
                break;
            }

            if (!transcodeResult.Success)
            {
                taskResult.Status = JobStatus.Failed;
                taskResult.Message = transcodeResult.ErrorMessage;
                ReportProgress(progress, task, "queue.failed", taskResult.ProgressPercent, taskResult.Speed, taskResult.Message);
                logCallback?.Invoke($"处理失败 {task.FileName}：{transcodeResult.ErrorMessage}");
                await CompleteTaskAsync(results, taskResult, onTaskCompletedAsync);
                continue;
            }

            ReportProgress(progress, task, "queue.validate-output", Math.Max(taskResult.ProgressPercent, 99d), taskResult.Speed, "正在校验输出文件");
            var validation = await _validateOutputAsync(
                task.InputPath,
                task.OutputPath,
                OutputValidationToleranceSeconds,
                cancellationToken);
            logCallback?.Invoke($"输出校验：{validation.Source} | 差值 {validation.DifferenceSeconds:0.000}s | {validation.Message}");

            if (!validation.IsMatch)
            {
                taskResult.Status = JobStatus.Failed;
                taskResult.Message = "输出文件校验失败";
                ReportProgress(progress, task, "queue.failed", taskResult.ProgressPercent, taskResult.Speed, taskResult.Message);
                logCallback?.Invoke($"处理失败 {task.FileName}：{validation.Message}");
                await CompleteTaskAsync(results, taskResult, onTaskCompletedAsync);
                continue;
            }

            taskResult.Status = JobStatus.Success;
            taskResult.ProgressPercent = 100d;
            taskResult.Speed = "done";
            taskResult.Message = "转换完成";
            ReportProgress(progress, task, "queue.success", 100d, "done", taskResult.Message);
            logCallback?.Invoke($"已完成 {task.FileName}");

            var shouldDeleteSource = task.DeleteSource ?? settings.DeleteSourceAfterSuccess;
            if (shouldDeleteSource && File.Exists(task.InputPath))
            {
                try
                {
                    File.Delete(task.InputPath);
                    taskResult.SourceDeleted = true;
                    logCallback?.Invoke($"已删除源文件：{task.InputPath}");
                }
                catch (Exception ex)
                {
                    logCallback?.Invoke($"警告：删除源文件失败：{task.InputPath} | {ex.Message}");
                }
            }

            await CompleteTaskAsync(results, taskResult, onTaskCompletedAsync);
        }

        return new TranscodeQueueExecutionResult
        {
            QueueWasCancelled = queueWasCancelled,
            TaskResults = results
        };
    }

    private static async Task CompleteTaskAsync(
        ICollection<TranscodeTaskResult> results,
        TranscodeTaskResult taskResult,
        Func<TranscodeTaskResult, Task>? onTaskCompletedAsync)
    {
        results.Add(taskResult);
        if (onTaskCompletedAsync is not null)
        {
            await onTaskCompletedAsync(taskResult);
        }
    }

    private static TranscodeTaskResult CreateTaskResult(TranscodeTaskSpec task)
    {
        return new TranscodeTaskResult
        {
            TaskId = task.TaskId,
            InputPath = task.InputPath,
            OutputPath = task.OutputPath,
            Status = JobStatus.Probing,
            Message = "正在读取媒体信息"
        };
    }

    private static void ApplyOverlayResult(TranscodeTaskResult taskResult, TranscodeOverlayPreparationResult overlay)
    {
        taskResult.SubtitleStreamOrdinal = overlay.SubtitleStreamOrdinal;
        taskResult.SubtitleAnalysisSource = overlay.SubtitleAnalysisSource;
        taskResult.SubtitleKindSummary = overlay.SubtitleKindSummary;
        taskResult.DanmakuSourceSummary = overlay.DanmakuSourceSummary;
        taskResult.DanmakuPreparationSummary = overlay.DanmakuPreparationSummary;
        taskResult.DanmakuXmlPath = overlay.DanmakuXmlPath;
        taskResult.DanmakuAssPath = overlay.DanmakuAssPath;
        taskResult.DanmakuXmlCommentCount = overlay.DanmakuXmlCommentCount;
        taskResult.DanmakuKeptCommentCount = overlay.DanmakuKeptCommentCount;
    }

    private static string BuildOverlayModeSummary(int? subtitleStreamOrdinal, string? danmakuAssPath)
    {
        var hasSubtitle = subtitleStreamOrdinal is not null;
        var hasDanmaku = !string.IsNullOrWhiteSpace(danmakuAssPath);

        return (hasSubtitle, hasDanmaku) switch
        {
            (true, true) => "字幕 + 弹幕",
            (true, false) => "字幕",
            (false, true) => "弹幕",
            _ => "原始画面"
        };
    }

    private static void ReportProgress(
        IProgress<WorkflowProgress>? progress,
        TranscodeTaskSpec task,
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
            ItemId = task.TaskId.ToString("D"),
            ItemPath = task.InputPath,
            Timestamp = DateTimeOffset.UtcNow
        });
    }
}
