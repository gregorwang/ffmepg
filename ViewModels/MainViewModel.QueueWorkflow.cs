using AnimeTranscoder.Models;
using AnimeTranscoder.Workflows;

namespace AnimeTranscoder.ViewModels;

public sealed partial class MainViewModel
{
    private const bool UseSharedQueueWorkflow = true;
    private readonly TranscodeQueueWorkflow _transcodeQueueWorkflow;

    private Task StartQueueAsync()
    {
        return UseSharedQueueWorkflow
            ? StartQueueWithWorkflowAsync()
            : StartQueueLegacyAsync();
    }

    private async Task StartQueueWithWorkflowAsync()
    {
        if (IsRunning || IsAudioExtracting || IsAudioSilenceDetecting || IsClipRunning || IsDouyinExporting)
        {
            return;
        }

        IsRunning = true;
        _runCancellationTokenSource = new CancellationTokenSource();
        var queueWasCancelled = false;

        try
        {
            Directory.CreateDirectory(Settings.OutputDirectory);

            var candidateJobs = Jobs.Where(job => job.Status is JobStatus.Pending or JobStatus.Failed).ToList();
            if (candidateJobs.Count == 0)
            {
                return;
            }

            var taskById = new Dictionary<Guid, TranscodeJob>(candidateJobs.Count);
            var taskSpecs = new List<TranscodeTaskSpec>(candidateJobs.Count);
            foreach (var job in candidateJobs)
            {
                PrepareJobForWorkflowRun(job);
                taskById[job.Id] = job;
                taskSpecs.Add(CreateTaskSpec(job));
            }

            var executionResult = await _transcodeQueueWorkflow.ExecuteAsync(
                taskSpecs,
                Settings,
                _isNvencAvailable,
                PrepareOverlayForWorkflowAsync,
                async taskResult =>
                {
                    if (!taskById.TryGetValue(taskResult.TaskId, out var job))
                    {
                        return;
                    }

                    ApplyWorkflowResultToJob(job, taskResult);
                    await RecordHistoryAsync(job);
                    RaiseQueueSummaryProperties();
                },
                new Progress<WorkflowProgress>(progress => OnQueueWorkflowProgress(progress, taskById)),
                AppendLog,
                _runCancellationTokenSource.Token);

            queueWasCancelled = executionResult.QueueWasCancelled;
        }
        catch (Exception ex)
        {
            AppendLog(ex.ToString());
            StatusMessage = "队列执行失败";
        }
        finally
        {
            IsRunning = false;
            _runCancellationTokenSource?.Dispose();
            _runCancellationTokenSource = null;
            StatusMessage = "队列处理结束";
            NotifyQueueCompleted(queueWasCancelled);
        }
    }

    private void PrepareJobForWorkflowRun(TranscodeJob job)
    {
        job.OutputPath = BuildOutputPath(job.InputPath);
        job.Speed = string.Empty;
        job.Progress = 0;
        job.Status = JobStatus.Pending;
        job.Message = string.Empty;
        job.SubtitleStreamOrdinal = null;
        job.SubtitleAnalysisSource = string.Empty;
        job.SubtitleKindSummary = string.Empty;
        job.DanmakuSourceSummary = string.Empty;
        job.DanmakuPreparationSummary = string.Empty;
        job.DanmakuXmlPath = string.Empty;
        job.DanmakuAssPath = string.Empty;
        job.DanmakuXmlCommentCount = 0;
        job.DanmakuKeptCommentCount = 0;
    }

    private TranscodeTaskSpec CreateTaskSpec(TranscodeJob job)
    {
        return new TranscodeTaskSpec
        {
            TaskId = job.Id,
            InputPath = job.InputPath,
            OutputPath = job.OutputPath,
            DanmakuInputPath = job.DanmakuInputPath,
            DanmakuExcludedCommentKeys = job.DanmakuExcludedCommentKeys
        };
    }

    private async Task<TranscodeOverlayPreparationResult> PrepareOverlayForWorkflowAsync(
        TranscodeTaskSpec task,
        MediaProbeResult probe,
        Action<string>? _,
        CancellationToken cancellationToken)
    {
        if (!TryGetJob(task.TaskId, out var job))
        {
            return TranscodeOverlayPreparationResult.Fail("找不到对应的队列任务。");
        }

        var overlay = await PrepareOverlayAssetsAsync(job, probe, cancellationToken);
        return overlay.Success
            ? TranscodeOverlayPreparationResult.SuccessState(
                overlay.SubtitleStreamOrdinal,
                overlay.DanmakuAssPath,
                overlay.DanmakuXmlPath,
                overlay.DanmakuXmlCommentCount,
                overlay.DanmakuKeptCommentCount,
                overlay.SubtitleAnalysisSource,
                overlay.SubtitleKindSummary,
                overlay.DanmakuSourceSummary,
                overlay.DanmakuPreparationSummary)
            : TranscodeOverlayPreparationResult.Fail(overlay.ErrorMessage);
    }

    private void OnQueueWorkflowProgress(
        WorkflowProgress progress,
        IReadOnlyDictionary<Guid, TranscodeJob> taskById)
    {
        if (!Guid.TryParse(progress.ItemId, out var taskId) ||
            !taskById.TryGetValue(taskId, out var job))
        {
            return;
        }

        switch (progress.Stage)
        {
            case "queue.probing":
                job.Status = JobStatus.Probing;
                break;
            case "queue.prepare-overlay":
            case "queue.transcoding":
            case "queue.validate-output":
                job.Status = JobStatus.Running;
                break;
        }

        job.Progress = Math.Round(progress.ProgressPercent, 2);
        if (!string.IsNullOrWhiteSpace(progress.Speed) &&
            !string.Equals(progress.Speed, "done", StringComparison.OrdinalIgnoreCase))
        {
            job.Speed = progress.Speed;
        }

        if (!string.IsNullOrWhiteSpace(progress.Message))
        {
            job.Message = progress.Message;
            StatusMessage = progress.Message;
        }
    }

    private void ApplyWorkflowResultToJob(TranscodeJob job, TranscodeTaskResult taskResult)
    {
        job.OutputPath = taskResult.OutputPath;
        job.Status = taskResult.Status;
        job.Progress = Math.Round(taskResult.ProgressPercent, 2);
        job.Speed = taskResult.Speed;
        job.Message = taskResult.Message;
        job.EncoderUsed = taskResult.EncoderUsed;
        job.SourceDurationSeconds = taskResult.SourceDurationSeconds;
        job.SubtitleStreamOrdinal = taskResult.SubtitleStreamOrdinal;
        job.SubtitleAnalysisSource = taskResult.SubtitleAnalysisSource;
        job.SubtitleKindSummary = taskResult.SubtitleKindSummary;
        job.DanmakuSourceSummary = taskResult.DanmakuSourceSummary;
        job.DanmakuPreparationSummary = taskResult.DanmakuPreparationSummary;
        job.DanmakuXmlPath = taskResult.DanmakuXmlPath;
        job.DanmakuAssPath = taskResult.DanmakuAssPath;
        job.DanmakuXmlCommentCount = taskResult.DanmakuXmlCommentCount;
        job.DanmakuKeptCommentCount = taskResult.DanmakuKeptCommentCount;
    }

    private bool TryGetJob(Guid taskId, out TranscodeJob job)
    {
        job = Jobs.FirstOrDefault(item => item.Id == taskId)!;
        return job is not null;
    }
}
