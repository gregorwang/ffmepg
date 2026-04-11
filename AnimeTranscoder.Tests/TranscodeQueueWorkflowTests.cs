using AnimeTranscoder.Models;
using AnimeTranscoder.Workflows;
using Xunit;

namespace AnimeTranscoder.Tests;

public sealed class TranscodeQueueWorkflowTests
{
    [Fact]
    public async Task ExecuteAsync_MarksMissingInputAsFailed()
    {
        var workflow = CreateWorkflow();
        var task = new TranscodeTaskSpec
        {
            TaskId = Guid.NewGuid(),
            InputPath = Path.Combine(Path.GetTempPath(), $"{Guid.NewGuid():N}.mp4"),
            OutputPath = Path.Combine(Path.GetTempPath(), $"{Guid.NewGuid():N}.mp4")
        };
        var completed = new List<TranscodeTaskResult>();

        var result = await workflow.ExecuteAsync(
            [task],
            CreateSettings(),
            isNvencAvailable: false,
            (_, _, _, _) => Task.FromResult(TranscodeOverlayPreparationResult.Fail("should-not-run")),
            taskResult =>
            {
                completed.Add(taskResult);
                return Task.CompletedTask;
            },
            progress: null,
            logCallback: null,
            cancellationToken: CancellationToken.None);

        var taskResult = Assert.Single(result.TaskResults);
        Assert.False(result.QueueWasCancelled);
        Assert.Equal(JobStatus.Failed, taskResult.Status);
        Assert.Equal("找不到输入文件", taskResult.Message);
        Assert.Single(completed);
    }

    [Fact]
    public async Task ExecuteAsync_SkipsWhenExistingOutputIsValid()
    {
        using var workspace = new TemporaryDirectory();
        var inputPath = workspace.CreateFile("input.mp4");
        var outputPath = workspace.PathFor("output.mp4");
        var validationCalls = 0;
        var workflow = CreateWorkflow(
            validateOutputAsync: (_, _, _, _) =>
            {
                validationCalls++;
                return Task.FromResult(new OutputValidationResult
                {
                    IsMatch = true,
                    Source = "test",
                    Message = "match"
                });
            });
        var task = new TranscodeTaskSpec
        {
            TaskId = Guid.NewGuid(),
            InputPath = inputPath,
            OutputPath = outputPath
        };

        var result = await workflow.ExecuteAsync(
            [task],
            CreateSettings(),
            isNvencAvailable: false,
            (_, _, _, _) => Task.FromResult(TranscodeOverlayPreparationResult.Fail("should-not-run")),
            onTaskCompletedAsync: null,
            progress: null,
            logCallback: null,
            cancellationToken: CancellationToken.None);

        var taskResult = Assert.Single(result.TaskResults);
        Assert.Equal(1, validationCalls);
        Assert.Equal(JobStatus.Skipped, taskResult.Status);
        Assert.Equal(100d, taskResult.ProgressPercent);
        Assert.Equal("已存在有效输出文件", taskResult.Message);
    }

    [Fact]
    public async Task ExecuteAsync_CompletesSuccessfulTaskAndDeletesSourceWhenConfigured()
    {
        using var workspace = new TemporaryDirectory();
        var inputPath = workspace.CreateFile("input.mp4");
        var outputPath = workspace.PathFor("output.mp4");
        var validationCalls = 0;
        var progressEvents = new List<WorkflowProgress>();
        var workflow = CreateWorkflow(
            validateOutputAsync: (_, _, _, _) =>
            {
                validationCalls++;
                return Task.FromResult(new OutputValidationResult
                {
                    IsMatch = validationCalls > 1,
                    Source = "test",
                    Message = validationCalls > 1 ? "validated" : "not-match"
                });
            },
            runTranscodeAsync: async (task, _, _, _, _, progressCallback, _, _) =>
            {
                progressCallback?.Invoke(42d, "1.8x");
                await File.WriteAllTextAsync(task.OutputPath, "output");
                return new TranscodeResult { Success = true };
            });
        var settings = CreateSettings();
        settings.DeleteSourceAfterSuccess = true;

        var result = await workflow.ExecuteAsync(
            [new TranscodeTaskSpec
            {
                TaskId = Guid.NewGuid(),
                InputPath = inputPath,
                OutputPath = outputPath
            }],
            settings,
            isNvencAvailable: false,
            (_, _, _, _) => Task.FromResult(TranscodeOverlayPreparationResult.SuccessState(
                subtitleStreamOrdinal: 0,
                danmakuAssPath: string.Empty,
                danmakuXmlPath: string.Empty,
                danmakuXmlCommentCount: 0,
                danmakuKeptCommentCount: 0,
                subtitleAnalysisSource: "test",
                subtitleKindSummary: "文本字幕 1 条，图片字幕 0 条",
                danmakuSourceSummary: "弹幕已关闭",
                danmakuPreparationSummary: "弹幕已关闭")),
            onTaskCompletedAsync: null,
            new Progress<WorkflowProgress>(progressEvents.Add),
            logCallback: null,
            cancellationToken: CancellationToken.None);

        var taskResult = Assert.Single(result.TaskResults);
        Assert.Equal(JobStatus.Success, taskResult.Status);
        Assert.Equal("转换完成", taskResult.Message);
        Assert.Equal("libx264", taskResult.EncoderUsed);
        Assert.True(taskResult.SourceDeleted);
        Assert.False(File.Exists(inputPath));
        Assert.Contains(progressEvents, item => item.Stage == "queue.probing");
        Assert.Contains(progressEvents, item => item.Stage == "queue.transcoding" && Math.Abs(item.ProgressPercent - 42d) < 0.001);
        Assert.Contains(progressEvents, item => item.Stage == "queue.success" && item.ItemId == taskResult.TaskId.ToString("D"));
    }

    [Fact]
    public async Task ExecuteAsync_MarksCurrentTaskAsCancelledWhenCancellationRequestedAfterTranscode()
    {
        using var workspace = new TemporaryDirectory();
        var inputPath = workspace.CreateFile("input.mp4");
        var outputPath = workspace.PathFor("output.mp4");
        using var cancellationTokenSource = new CancellationTokenSource();
        var workflow = CreateWorkflow(
            validateOutputAsync: (_, _, _, _) => Task.FromResult(new OutputValidationResult
            {
                IsMatch = false,
                Source = "test",
                Message = "not-match"
            }),
            runTranscodeAsync: (_, _, _, _, _, _, _, _) =>
            {
                cancellationTokenSource.Cancel();
                return Task.FromResult(new TranscodeResult { Success = true });
            });

        var result = await workflow.ExecuteAsync(
            [new TranscodeTaskSpec
            {
                TaskId = Guid.NewGuid(),
                InputPath = inputPath,
                OutputPath = outputPath
            }],
            CreateSettings(),
            isNvencAvailable: false,
            (_, _, _, _) => Task.FromResult(TranscodeOverlayPreparationResult.SuccessState(
                subtitleStreamOrdinal: 0,
                danmakuAssPath: string.Empty,
                danmakuXmlPath: string.Empty,
                danmakuXmlCommentCount: 0,
                danmakuKeptCommentCount: 0,
                subtitleAnalysisSource: "test",
                subtitleKindSummary: "文本字幕 1 条，图片字幕 0 条",
                danmakuSourceSummary: "弹幕已关闭",
                danmakuPreparationSummary: "弹幕已关闭")),
            onTaskCompletedAsync: null,
            progress: null,
            logCallback: null,
            cancellationToken: cancellationTokenSource.Token);

        var taskResult = Assert.Single(result.TaskResults);
        Assert.True(result.QueueWasCancelled);
        Assert.Equal(JobStatus.Cancelled, taskResult.Status);
        Assert.Equal("任务已取消", taskResult.Message);
    }

    [Fact]
    public async Task ExecuteAsync_WhenSecondTaskFails_ThirdTaskStillExecutes()
    {
        using var workspace = new TemporaryDirectory();
        var tasks = Enumerable.Range(1, 3).Select(index => new TranscodeTaskSpec
        {
            TaskId = Guid.NewGuid(),
            InputPath = workspace.CreateFile($"input-{index}.mp4"),
            OutputPath = workspace.PathFor($"out/output-{index}.mp4")
        }).ToList();
        var runOrder = new List<string>();
        var workflow = CreateWorkflow(
            validateOutputAsync: (_, outputPath, _, _) => Task.FromResult(new OutputValidationResult
            {
                IsMatch = File.Exists(outputPath),
                Source = "test",
                Message = "validated"
            }),
            runTranscodeAsync: async (task, _, _, _, _, _, _, _) =>
            {
                runOrder.Add(task.FileName);
                if (task == tasks[1])
                {
                    return new TranscodeResult { Success = false, ErrorMessage = "ffmpeg exited with code 1" };
                }

                Directory.CreateDirectory(Path.GetDirectoryName(task.OutputPath)!);
                await File.WriteAllTextAsync(task.OutputPath, "ok");
                return new TranscodeResult { Success = true };
            });

        var result = await workflow.ExecuteAsync(
            tasks,
            CreateSettings(),
            isNvencAvailable: false,
            (_, _, _, _) => Task.FromResult(TranscodeOverlayPreparationResult.SuccessState(null, "", "", 0, 0, "", "", "", "")),
            onTaskCompletedAsync: null,
            progress: null,
            logCallback: null,
            cancellationToken: CancellationToken.None);

        Assert.Equal(3, runOrder.Count);
        Assert.Equal(JobStatus.Success, result.TaskResults[0].Status);
        Assert.Equal(JobStatus.Failed, result.TaskResults[1].Status);
        Assert.Equal(JobStatus.Success, result.TaskResults[2].Status);
    }

    [Fact]
    public async Task ExecuteAsync_WhenCancelledDuringSecondTask_ThirdTaskDoesNotExecute()
    {
        using var workspace = new TemporaryDirectory();
        using var cancellationTokenSource = new CancellationTokenSource();
        var tasks = Enumerable.Range(1, 3).Select(index => new TranscodeTaskSpec
        {
            TaskId = Guid.NewGuid(),
            InputPath = workspace.CreateFile($"input-{index}.mp4"),
            OutputPath = workspace.PathFor($"out/output-{index}.mp4")
        }).ToList();
        var runCount = 0;
        var workflow = CreateWorkflow(
            runTranscodeAsync: (task, _, _, _, _, _, _, _) =>
            {
                runCount++;
                if (task == tasks[1])
                {
                    cancellationTokenSource.Cancel();
                }

                return Task.FromResult(new TranscodeResult { Success = true });
            });

        var result = await workflow.ExecuteAsync(
            tasks,
            CreateSettings(),
            isNvencAvailable: false,
            (_, _, _, _) => Task.FromResult(TranscodeOverlayPreparationResult.SuccessState(null, "", "", 0, 0, "", "", "", "")),
            onTaskCompletedAsync: null,
            progress: null,
            logCallback: null,
            cancellationToken: cancellationTokenSource.Token);

        Assert.True(result.QueueWasCancelled);
        Assert.Equal(2, runCount);
        Assert.Equal(JobStatus.Cancelled, result.TaskResults[1].Status);
        Assert.DoesNotContain(result.TaskResults, item => item.InputPath == tasks[2].InputPath);
    }

    [Fact]
    public async Task ExecuteAsync_FailsWhenTranscodeReturnsError()
    {
        using var workspace = new TemporaryDirectory();
        var inputPath = workspace.CreateFile("input.mp4");
        var outputPath = workspace.PathFor("out/output.mp4");
        var workflow = CreateWorkflow(
            runTranscodeAsync: (_, _, _, _, _, _, _, _) =>
                Task.FromResult(new TranscodeResult { Success = false, ErrorMessage = "ffmpeg exited with code 1" }));

        var result = await workflow.ExecuteAsync(
            [new TranscodeTaskSpec { TaskId = Guid.NewGuid(), InputPath = inputPath, OutputPath = outputPath }],
            CreateSettings(),
            isNvencAvailable: false,
            (_, _, _, _) => Task.FromResult(TranscodeOverlayPreparationResult.SuccessState(null, "", "", 0, 0, "", "", "", "")),
            onTaskCompletedAsync: null,
            progress: null,
            logCallback: null,
            cancellationToken: CancellationToken.None);

        var taskResult = Assert.Single(result.TaskResults);
        Assert.Equal(JobStatus.Failed, taskResult.Status);
        Assert.Equal("ffmpeg exited with code 1", taskResult.Message);
    }

    [Fact]
    public async Task ExecuteAsync_DeleteSourceLockedLogsWarningButTaskStillSucceeds()
    {
        using var workspace = new TemporaryDirectory();
        var inputPath = workspace.CreateFile("input.mp4");
        var outputPath = workspace.PathFor("out/output.mp4");
        using var lockStream = new FileStream(inputPath, FileMode.Open, FileAccess.Read, FileShare.None);
        var logs = new List<string>();
        var workflow = CreateWorkflow(
            validateOutputAsync: (_, path, _, _) => Task.FromResult(new OutputValidationResult
            {
                IsMatch = File.Exists(path),
                Source = "test",
                Message = "validated"
            }),
            runTranscodeAsync: async (task, _, _, _, _, _, _, _) =>
            {
                Directory.CreateDirectory(Path.GetDirectoryName(task.OutputPath)!);
                await File.WriteAllTextAsync(task.OutputPath, "ok");
                return new TranscodeResult { Success = true };
            });
        var settings = CreateSettings();
        settings.DeleteSourceAfterSuccess = true;

        var result = await workflow.ExecuteAsync(
            [new TranscodeTaskSpec { TaskId = Guid.NewGuid(), InputPath = inputPath, OutputPath = outputPath }],
            settings,
            isNvencAvailable: false,
            (_, _, _, _) => Task.FromResult(TranscodeOverlayPreparationResult.SuccessState(null, "", "", 0, 0, "", "", "", "")),
            onTaskCompletedAsync: null,
            progress: null,
            logCallback: logs.Add,
            cancellationToken: CancellationToken.None);

        var taskResult = Assert.Single(result.TaskResults);
        Assert.Equal(JobStatus.Success, taskResult.Status);
        Assert.False(taskResult.SourceDeleted);
        Assert.Contains(logs, item => item.Contains("警告：删除源文件失败", StringComparison.Ordinal));
    }

    [Fact]
    public async Task ExecuteAsync_FailsWhenStoragePreflightFails()
    {
        using var workspace = new TemporaryDirectory();
        var inputPath = workspace.CreateFile("input.mp4");
        var outputPath = workspace.PathFor("nested/out/output.mp4");
        var workflow = CreateWorkflow(
            validateOutputPath: (_, _, _) => new StoragePreflightResult
            {
                HasEnoughSpace = false,
                Message = "disk-low"
            });

        var result = await workflow.ExecuteAsync(
            [new TranscodeTaskSpec { TaskId = Guid.NewGuid(), InputPath = inputPath, OutputPath = outputPath }],
            CreateSettings(),
            isNvencAvailable: false,
            (_, _, _, _) => Task.FromResult(TranscodeOverlayPreparationResult.SuccessState(null, "", "", 0, 0, "", "", "", "")),
            onTaskCompletedAsync: null,
            progress: null,
            logCallback: null,
            cancellationToken: CancellationToken.None);

        var taskResult = Assert.Single(result.TaskResults);
        Assert.Equal(JobStatus.Failed, taskResult.Status);
        Assert.Equal("输出目录空间不足", taskResult.Message);
    }

    [Fact]
    public async Task ExecuteAsync_ReportsIncreasingProgress()
    {
        using var workspace = new TemporaryDirectory();
        var inputPath = workspace.CreateFile("input.mp4");
        var outputPath = workspace.PathFor("out/output.mp4");
        var progressEvents = new List<WorkflowProgress>();
        var workflow = CreateWorkflow(
            validateOutputAsync: (_, path, _, _) => Task.FromResult(new OutputValidationResult
            {
                IsMatch = File.Exists(path),
                Source = "test",
                Message = "validated"
            }),
            runTranscodeAsync: async (task, _, _, _, _, progressCallback, _, _) =>
            {
                progressCallback?.Invoke(10d, "1.0x");
                progressCallback?.Invoke(55d, "1.2x");
                progressCallback?.Invoke(80d, "1.4x");
                Directory.CreateDirectory(Path.GetDirectoryName(task.OutputPath)!);
                await File.WriteAllTextAsync(task.OutputPath, "ok");
                return new TranscodeResult { Success = true };
            });

        await workflow.ExecuteAsync(
            [new TranscodeTaskSpec { TaskId = Guid.NewGuid(), InputPath = inputPath, OutputPath = outputPath }],
            CreateSettings(),
            isNvencAvailable: false,
            (_, _, _, _) => Task.FromResult(TranscodeOverlayPreparationResult.SuccessState(null, "", "", 0, 0, "", "", "", "")),
            onTaskCompletedAsync: null,
            progress: new Progress<WorkflowProgress>(progressEvents.Add),
            logCallback: null,
            cancellationToken: CancellationToken.None);

        var transcodeProgress = progressEvents
            .Where(item => item.Stage == "queue.transcoding")
            .Select(item => item.ProgressPercent)
            .ToList();

        Assert.Equal([10d, 55d, 80d], transcodeProgress);
    }

    private static TranscodeQueueWorkflow CreateWorkflow(
        Func<string, string, int, CancellationToken, Task<OutputValidationResult>>? validateOutputAsync = null,
        Func<string, string, AppSettings, StoragePreflightResult>? validateOutputPath = null,
        Func<string, CancellationToken, Task<MediaProbeResult?>>? probeMediaAsync = null,
        Func<string, bool, string>? resolveVideoEncoder = null,
        Func<TranscodeTaskSpec, MediaProbeResult, TranscodeOverlayPreparationResult, AppSettings, string, Action<double, string>?, Action<string>?, CancellationToken, Task<TranscodeResult>>? runTranscodeAsync = null)
    {
        return new TranscodeQueueWorkflow(
            validateOutputAsync ?? ((_, _, _, _) => Task.FromResult(new OutputValidationResult
            {
                IsMatch = false,
                Source = "test",
                Message = "not-match"
            })),
            validateOutputPath ?? ((_, _, _) => new StoragePreflightResult
            {
                HasEnoughSpace = true,
                Message = "space-ok"
            }),
            probeMediaAsync ?? ((inputPath, _) => Task.FromResult<MediaProbeResult?>(new MediaProbeResult
            {
                Path = inputPath,
                Duration = TimeSpan.FromSeconds(12),
                Message = "probe-ok"
            })),
            resolveVideoEncoder ?? ((_, _) => "libx264"),
            runTranscodeAsync ?? ((_, _, _, _, _, _, _, _) => Task.FromResult(new TranscodeResult { Success = true })));
    }

    private static AppSettings CreateSettings()
    {
        var settings = AppSettings.CreateDefault(Path.GetTempPath());
        settings.OverwriteExisting = false;
        settings.DeleteSourceAfterSuccess = false;
        settings.EnableDanmaku = false;
        settings.BurnEmbeddedSubtitles = true;
        return settings;
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            DirectoryPath = Path.Combine(Path.GetTempPath(), "AnimeTranscoder.Tests", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(DirectoryPath);
        }

        public string DirectoryPath { get; }

        public string CreateFile(string name)
        {
            var path = Path.Combine(DirectoryPath, name);
            File.WriteAllText(path, "test");
            return path;
        }

        public string PathFor(string name)
        {
            return Path.Combine(DirectoryPath, name);
        }

        public void Dispose()
        {
            if (Directory.Exists(DirectoryPath))
            {
                Directory.Delete(DirectoryPath, recursive: true);
            }
        }
    }
}
