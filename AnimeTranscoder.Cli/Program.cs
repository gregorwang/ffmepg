using System.Globalization;
using System.Text.Json;
using System.Text.Json.Serialization;
using AnimeTranscoder.Models;
using AnimeTranscoder.Services;
using AnimeTranscoder.Workflows;

namespace AnimeTranscoder.Cli;

internal static class Program
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
        Converters = { new JsonStringEnumConverter() }
    };

    public static async Task<int> Main(string[] args)
    {
        using var cancellationTokenSource = new CancellationTokenSource();
        Console.CancelKeyPress += (_, eventArgs) =>
        {
            eventArgs.Cancel = true;
            cancellationTokenSource.Cancel();
        };

        if (args.Length == 0)
        {
            PrintHelp();
            return CliExitCodes.ValidationError;
        }

        var services = BuildServices();

        try
        {
            return await DispatchAsync(args, services, cancellationTokenSource.Token);
        }
        catch (OperationCanceledException)
        {
            WriteJson(new { success = false, error = "已取消" });
            return CliExitCodes.Cancelled;
        }
        catch (ArgumentException ex)
        {
            Console.Error.WriteLine(ex.Message);
            WriteJson(new { success = false, error = ex.Message });
            return CliExitCodes.ValidationError;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(ex.Message);
            WriteJson(new { success = false, error = ex.Message });
            return CliExitCodes.Failure;
        }
    }

    private static async Task<int> DispatchAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        return args[0].ToLowerInvariant() switch
        {
            "probe" => await HandleProbeAsync(args[1..], services, cancellationToken),
            "audio" => await HandleAudioAsync(args[1..], services, cancellationToken),
            "project" => await HandleProjectAsync(args[1..], services, cancellationToken),
            "transcript" => await HandleTranscriptAsync(args[1..], services, cancellationToken),
            "selection" => await HandleSelectionAsync(args[1..], services, cancellationToken),
            "transcode" => await HandleTranscodeAsync(args[1..], services, cancellationToken),
            "help" or "--help" or "-h" => HandleHelp(),
            _ => throw new ArgumentException($"未知命令：{args[0]}")
        };
    }

    private static async Task<int> HandleProbeAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        var options = ParseOptions(args);
        ValidateOptions(options, ["input"]);
        var inputPath = GetRequiredOption(options, "input");
        var result = await services.MediaProbeWorkflow.ProbeAsync(inputPath, cancellationToken);
        WriteJson(result);
        return CliExitCodes.Success;
    }

    private static async Task<int> HandleAudioAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        if (args.Length == 0)
        {
            throw new ArgumentException("audio 命令缺少子命令。");
        }

        return args[0].ToLowerInvariant() switch
        {
            "extract" => await HandleAudioExtractAsync(args[1..], services, cancellationToken),
            "detect-silence" => await HandleAudioDetectSilenceAsync(args[1..], services, cancellationToken),
            "export-work" => await HandleAudioExportWorkAsync(args[1..], services, cancellationToken),
            "render-selection" => await HandleAudioRenderSelectionAsync(args[1..], services, cancellationToken),
            _ => throw new ArgumentException($"未知 audio 子命令：{args[0]}")
        };
    }

    private static async Task<int> HandleAudioExtractAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        var options = ParseOptions(args);
        ValidateOptions(options, ["input", "output", "format", "track", "start", "duration", "normalize", "bitrate", "progress"]);
        var inputPath = GetRequiredOption(options, "input");
        var outputPath = GetRequiredOption(options, "output");
        var format = ParseEnumOption(options, "format", AudioFormat.AAC);
        var trackIndex = GetOptionalInt(options, "track");
        var startTime = GetOptionalTimeSpan(options, "start");
        var duration = GetOptionalTimeSpan(options, "duration");
        var normalize = GetOptionalBool(options, "normalize") ?? false;
        var bitrateKbps = GetOptionalInt(options, "bitrate") ?? 192;
        var progressReporter = CreateProgressReporter(options);
        var probe = await services.FfprobeService.ProbeAsync(inputPath, cancellationToken)
            ?? throw new InvalidOperationException("媒体探测失败。");

        var effectiveDuration = duration?.TotalSeconds
            ?? Math.Max((probe.Duration - (startTime ?? TimeSpan.Zero)).TotalSeconds, 0d);

        var result = await services.AudioProcessingWorkflow.ExtractAsync(
            inputPath,
            outputPath,
            format,
            trackIndex,
            startTime,
            duration,
            normalize,
            bitrateKbps,
            effectiveDuration,
            progressReporter,
            cancellationToken);

        WriteJson(new
        {
            success = result.Success,
            outputPath = result.OutputPath,
            errorMessage = result.ErrorMessage
        });

        return ResolveExitCode(result.ErrorMessage, result.Success);
    }

    private static async Task<int> HandleAudioDetectSilenceAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        var options = ParseOptions(args);
        ValidateOptions(options, ["input", "track", "threshold", "min-duration"]);
        var inputPath = GetRequiredOption(options, "input");
        var trackIndex = GetOptionalInt(options, "track");
        var threshold = GetOptionalDouble(options, "threshold") ?? -30d;
        var minimumDuration = GetOptionalDouble(options, "min-duration") ?? 2d;

        var segments = await services.AudioProcessingWorkflow.DetectSilenceAsync(
            inputPath,
            trackIndex,
            threshold,
            minimumDuration,
            CreateProgressReporter(options),
            cancellationToken);

        WriteJson(new
        {
            success = true,
            inputPath = Path.GetFullPath(inputPath),
            trackIndex,
            thresholdDb = threshold,
            minimumDurationSeconds = minimumDuration,
            segments
        });

        return CliExitCodes.Success;
    }

    private static async Task<int> HandleAudioExportWorkAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        var options = ParseOptions(args);
        ValidateOptions(options, ["project", "track", "sample-rate", "progress"]);
        var projectPath = GetRequiredOption(options, "project");
        var trackIndex = GetOptionalInt(options, "track");
        var sampleRate = GetOptionalInt(options, "sample-rate") ?? 16000;
        var progressReporter = CreateProgressReporter(options);

        var result = await services.ProjectAudioWorkflow.ExportWorkAudioAsync(
            projectPath,
            trackIndex,
            sampleRate,
            progressReporter,
            cancellationToken);

        WriteJson(new
        {
            success = result.Success,
            outputPath = result.OutputPath,
            errorMessage = result.ErrorMessage
        });

        return ResolveExitCode(result.ErrorMessage, result.Success);
    }

    private static async Task<int> HandleAudioRenderSelectionAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        var options = ParseOptions(args);
        ValidateOptions(options, ["project", "output", "mode", "progress"]);
        var projectPath = GetRequiredOption(options, "project");
        var outputPath = GetRequiredOption(options, "output");
        var mode = ParseEnumOption(options, "mode", AudioRenderMode.PreserveTimeline);
        var progressReporter = CreateProgressReporter(options);

        var result = await services.ProjectAudioWorkflow.RenderSelectionAsync(
            projectPath,
            outputPath,
            mode,
            progressReporter,
            cancellationToken);

        WriteJson(new
        {
            success = result.Success,
            outputPath = result.OutputPath,
            errorMessage = result.ErrorMessage,
            mode
        });

        return ResolveExitCode(result.ErrorMessage, result.Success);
    }

    private static async Task<int> HandleProjectAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        if (args.Length == 0)
        {
            throw new ArgumentException("project 命令缺少子命令。");
        }

        return args[0].ToLowerInvariant() switch
        {
            "init" => await HandleProjectInitAsync(args[1..], services, cancellationToken),
            "show" => await HandleProjectShowAsync(args[1..], services, cancellationToken),
            _ => throw new ArgumentException($"未知 project 子命令：{args[0]}")
        };
    }

    private static async Task<int> HandleProjectInitAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        var options = ParseOptions(args);
        ValidateOptions(options, ["input", "project"]);
        var inputPath = GetRequiredOption(options, "input");
        var projectPath = GetRequiredOption(options, "project");
        var project = await services.ProjectAudioWorkflow.InitializeAsync(inputPath, projectPath, cancellationToken);
        WriteJson(new
        {
            success = true,
            projectPath = Path.GetFullPath(projectPath),
            project
        });

        return CliExitCodes.Success;
    }

    private static async Task<int> HandleProjectShowAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        var options = ParseOptions(args);
        ValidateOptions(options, ["project"]);
        var projectPath = GetRequiredOption(options, "project");
        var project = await services.ProjectFileService.LoadAsync(projectPath, cancellationToken);
        WriteJson(project);
        return CliExitCodes.Success;
    }

    private static async Task<int> HandleTranscriptAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        if (args.Length == 0)
        {
            throw new ArgumentException("transcript 命令缺少子命令。");
        }

        return args[0].ToLowerInvariant() switch
        {
            "import" => await HandleTranscriptImportAsync(args[1..], services, cancellationToken),
            "generate" => await HandleTranscriptGenerateAsync(args[1..], services, cancellationToken),
            _ => throw new ArgumentException($"未知 transcript 子命令：{args[0]}")
        };
    }

    private static async Task<int> HandleTranscriptImportAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        var options = ParseOptions(args);
        ValidateOptions(options, ["project", "input"]);
        var projectPath = GetRequiredOption(options, "project");
        var inputPath = GetRequiredOption(options, "input");
        var project = await services.ProjectAudioWorkflow.ImportTranscriptAsync(projectPath, inputPath, cancellationToken);

        WriteJson(new
        {
            success = true,
            projectPath = Path.GetFullPath(projectPath),
            transcriptPath = project.TranscriptPath
        });

        return CliExitCodes.Success;
    }

    private static async Task<int> HandleTranscriptGenerateAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        var options = ParseOptions(args);
        ValidateOptions(options, ["project", "whisper-exe", "model", "language", "threads", "extra-args", "progress"]);

        var projectPath = ResolveProjectPathArgument(GetRequiredOption(options, "project"));
        var whisperOptions = ResolveWhisperOptions(options, projectPath);
        var progressReporter = CreatePercentProgressReporter(options, "transcript.generate");
        var project = await services.ProjectAudioWorkflow.GenerateTranscriptAsync(projectPath, whisperOptions, progressReporter, cancellationToken);
        var transcript = await services.TranscriptDocumentService.LoadAsync(project.TranscriptPath, cancellationToken);

        WriteJson(new
        {
            success = true,
            projectPath = Path.GetFullPath(projectPath),
            transcriptPath = project.TranscriptPath,
            segmentCount = transcript.Segments.Count
        });

        return CliExitCodes.Success;
    }

    private static async Task<int> HandleSelectionAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        if (args.Length == 0 || !string.Equals(args[0], "import", StringComparison.OrdinalIgnoreCase))
        {
            throw new ArgumentException("selection 目前只支持 import 子命令。");
        }

        var options = ParseOptions(args[1..]);
        ValidateOptions(options, ["project", "input"]);
        var projectPath = GetRequiredOption(options, "project");
        var inputPath = GetRequiredOption(options, "input");
        var project = await services.ProjectAudioWorkflow.ImportSelectionAsync(projectPath, inputPath, cancellationToken);

        WriteJson(new
        {
            success = true,
            projectPath = Path.GetFullPath(projectPath),
            selectionPath = project.SelectionPath
        });

        return CliExitCodes.Success;
    }

    private static async Task<int> HandleTranscodeAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        if (args.Length == 0)
        {
            throw new ArgumentException("transcode 命令缺少子命令。");
        }

        return args[0].ToLowerInvariant() switch
        {
            "run" => await HandleTranscodeRunAsync(args[1..], services, cancellationToken),
            "queue" => await HandleTranscodeQueueAsync(args[1..], services, cancellationToken),
            _ => throw new ArgumentException($"未知 transcode 子命令：{args[0]}")
        };
    }

    private static async Task<int> HandleTranscodeRunAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        var options = ParseOptions(args);
        ValidateOptions(options, ["input", "output", "preset", "no-overlay", "progress"]);

        var task = new TranscodeTaskSpec
        {
            TaskId = Guid.NewGuid(),
            InputPath = GetRequiredOption(options, "input"),
            OutputPath = GetRequiredOption(options, "output"),
            Preset = GetOptionalString(options, "preset") ?? "default",
            NoOverlay = GetOptionalBool(options, "no-overlay") ?? false
        };

        var queueResult = await ExecuteTranscodeQueueAsync(
            services,
            [task],
            CreateProgressReporter(options),
            CreateJsonLogWriter(options),
            cancellationToken);

        WriteJson(new
        {
            success = queueResult.TaskResults.All(item => item.Status is JobStatus.Success or JobStatus.Skipped),
            queueWasCancelled = queueResult.QueueWasCancelled,
            summary = BuildSummary(queueResult),
            tasks = queueResult.TaskResults
        });

        return ResolveQueueExitCode(queueResult);
    }

    private static async Task<int> HandleTranscodeQueueAsync(string[] args, ServiceContainer services, CancellationToken cancellationToken)
    {
        var options = ParseOptions(args);
        ValidateOptions(options, ["spec", "progress"]);

        var tasks = await LoadTranscodeTasksAsync(GetRequiredOption(options, "spec"), cancellationToken);
        var queueResult = await ExecuteTranscodeQueueAsync(
            services,
            tasks,
            CreateProgressReporter(options),
            CreateJsonLogWriter(options),
            cancellationToken);

        WriteJson(new
        {
            success = queueResult.TaskResults.All(item => item.Status is JobStatus.Success or JobStatus.Skipped),
            queueWasCancelled = queueResult.QueueWasCancelled,
            summary = BuildSummary(queueResult),
            tasks = queueResult.TaskResults
        });

        return ResolveQueueExitCode(queueResult);
    }

    private static int HandleHelp()
    {
        PrintHelp();
        return CliExitCodes.Success;
    }

    private static ServiceContainer BuildServices()
    {
        var ffmpegCommandBuilder = new FfmpegCommandBuilder();
        var ffprobeService = new FfprobeService();
        var ffmpegRunner = new FfmpegRunner(ffmpegCommandBuilder);
        var audioCommandBuilder = new AudioCommandBuilder();
        var audioExtractionService = new AudioExtractionService(ffmpegRunner, audioCommandBuilder);
        var audioProcessingWorkflow = new AudioProcessingWorkflow(audioExtractionService);
        var projectFileService = new ProjectFileService();
        var transcriptDocumentService = new TranscriptDocumentService();
        var selectionDocumentService = new SelectionDocumentService();
        var audioSelectionRenderService = new AudioSelectionRenderService(ffmpegRunner, ffprobeService);
        var whisperCliAdapter = new WhisperCliAdapter(audioExtractionService);
        var nativeMediaCoreService = new NativeMediaCoreService();
        var outputValidationService = new OutputValidationService(ffprobeService, nativeMediaCoreService);
        var storagePreflightService = new StoragePreflightService();
        var hardwareDetectionService = new HardwareDetectionService();
        var danmakuBurnCommandBuilder = new DanmakuBurnCommandBuilder(ffmpegCommandBuilder);

        return new ServiceContainer
        {
            FfprobeService = ffprobeService,
            AudioExtractionService = audioExtractionService,
            AudioProcessingWorkflow = audioProcessingWorkflow,
            ProjectFileService = projectFileService,
            TranscriptDocumentService = transcriptDocumentService,
            MediaProbeWorkflow = new MediaProbeWorkflow(ffprobeService),
            HardwareDetectionService = hardwareDetectionService,
            ProjectAudioWorkflow = new ProjectAudioWorkflow(
                projectFileService,
                transcriptDocumentService,
                selectionDocumentService,
                audioExtractionService,
                audioSelectionRenderService,
                ffprobeService,
                whisperCliAdapter),
            TranscodeQueueWorkflow = new TranscodeQueueWorkflow(
                outputValidationService,
                storagePreflightService,
                nativeMediaCoreService,
                ffprobeService,
                hardwareDetectionService,
                danmakuBurnCommandBuilder,
                ffmpegRunner)
        };
    }

    private static Dictionary<string, string?> ParseOptions(string[] args)
    {
        var options = new Dictionary<string, string?>(StringComparer.OrdinalIgnoreCase);
        for (var index = 0; index < args.Length; index++)
        {
            var token = args[index];
            if (!token.StartsWith("--", StringComparison.Ordinal))
            {
                throw new ArgumentException($"无法解析参数：{token}");
            }

            var key = token[2..];
            if (index + 1 < args.Length && !args[index + 1].StartsWith("--", StringComparison.Ordinal))
            {
                options[key] = args[index + 1];
                index++;
            }
            else
            {
                options[key] = "true";
            }
        }

        return options;
    }

    private static void ValidateOptions(IReadOnlyDictionary<string, string?> options, IEnumerable<string> allowedKeys)
    {
        var allowed = new HashSet<string>(allowedKeys, StringComparer.OrdinalIgnoreCase);
        foreach (var key in options.Keys)
        {
            if (!allowed.Contains(key))
            {
                throw new ArgumentException($"未知参数 --{key}");
            }
        }
    }

    private static string GetRequiredOption(IReadOnlyDictionary<string, string?> options, string key)
    {
        if (!options.TryGetValue(key, out var value) || string.IsNullOrWhiteSpace(value))
        {
            throw new ArgumentException($"缺少必填参数 --{key}");
        }

        return value;
    }

    private static string? GetOptionalString(IReadOnlyDictionary<string, string?> options, string key)
    {
        return options.TryGetValue(key, out var value) && !string.IsNullOrWhiteSpace(value)
            ? value
            : null;
    }

    private static int? GetOptionalInt(IReadOnlyDictionary<string, string?> options, string key)
    {
        return options.TryGetValue(key, out var value) && !string.IsNullOrWhiteSpace(value)
            ? int.Parse(value, CultureInfo.InvariantCulture)
            : null;
    }

    private static int? GetOptionalInt(string? value)
    {
        return !string.IsNullOrWhiteSpace(value)
            ? int.Parse(value, CultureInfo.InvariantCulture)
            : null;
    }

    private static double? GetOptionalDouble(IReadOnlyDictionary<string, string?> options, string key)
    {
        return options.TryGetValue(key, out var value) && !string.IsNullOrWhiteSpace(value)
            ? double.Parse(value, CultureInfo.InvariantCulture)
            : null;
    }

    private static bool? GetOptionalBool(IReadOnlyDictionary<string, string?> options, string key)
    {
        return options.TryGetValue(key, out var value) && !string.IsNullOrWhiteSpace(value)
            ? bool.Parse(value)
            : null;
    }

    private static TimeSpan? GetOptionalTimeSpan(IReadOnlyDictionary<string, string?> options, string key)
    {
        if (!options.TryGetValue(key, out var value) || string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        if (TimeSpan.TryParse(value, CultureInfo.InvariantCulture, out var timeSpan))
        {
            return timeSpan;
        }

        if (double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var seconds))
        {
            return TimeSpan.FromSeconds(seconds);
        }

        throw new ArgumentException($"参数 --{key} 的时间格式无效：{value}");
    }

    private static TEnum ParseEnumOption<TEnum>(
        IReadOnlyDictionary<string, string?> options,
        string key,
        TEnum defaultValue)
        where TEnum : struct, Enum
    {
        if (!options.TryGetValue(key, out var value) || string.IsNullOrWhiteSpace(value))
        {
            return defaultValue;
        }

        if (Enum.TryParse<TEnum>(value, ignoreCase: true, out var parsed))
        {
            return parsed;
        }

        throw new ArgumentException($"参数 --{key} 的值无效：{value}");
    }

    private static IProgress<WorkflowProgress>? CreateProgressReporter(IReadOnlyDictionary<string, string?> options)
    {
        if (!options.TryGetValue("progress", out var progressMode) ||
            !string.Equals(progressMode, "jsonl", StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        return new Progress<WorkflowProgress>(progress =>
        {
            var payload = new
            {
                type = "progress",
                stage = progress.Stage,
                percent = Math.Round(progress.ProgressPercent / 100d, 4),
                speed = progress.Speed,
                message = progress.Message,
                timestamp = progress.Timestamp
            };
            Console.Error.WriteLine(JsonSerializer.Serialize(payload, JsonOptions));
        });
    }

    private static IProgress<double>? CreatePercentProgressReporter(IReadOnlyDictionary<string, string?> options, string stage)
    {
        if (!options.TryGetValue("progress", out var progressMode) ||
            !string.Equals(progressMode, "jsonl", StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        return new Progress<double>(progress =>
        {
            var payload = new
            {
                type = "progress",
                stage,
                percent = Math.Round(progress / 100d, 4),
                message = $"正在执行 {stage}",
                timestamp = DateTimeOffset.UtcNow
            };
            Console.Error.WriteLine(JsonSerializer.Serialize(payload, JsonOptions));
        });
    }

    private static Action<string>? CreateJsonLogWriter(IReadOnlyDictionary<string, string?> options)
    {
        if (!options.TryGetValue("progress", out var progressMode) ||
            !string.Equals(progressMode, "jsonl", StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        return message =>
        {
            var payload = new
            {
                type = "log",
                message,
                timestamp = DateTimeOffset.UtcNow
            };
            Console.Error.WriteLine(JsonSerializer.Serialize(payload, JsonOptions));
        };
    }

    private static int ResolveExitCode(string? errorMessage, bool success)
    {
        if (success)
        {
            return CliExitCodes.Success;
        }

        return string.Equals(errorMessage, "已取消", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(errorMessage, "Cancelled", StringComparison.OrdinalIgnoreCase)
            ? CliExitCodes.Cancelled
            : CliExitCodes.Failure;
    }

    private static int ResolveQueueExitCode(TranscodeQueueExecutionResult result)
    {
        if (result.QueueWasCancelled || result.TaskResults.Any(item => item.Status == JobStatus.Cancelled))
        {
            return CliExitCodes.Cancelled;
        }

        return result.TaskResults.All(item => item.Status is JobStatus.Success or JobStatus.Skipped)
            ? CliExitCodes.Success
            : CliExitCodes.Failure;
    }

    private static object BuildSummary(TranscodeQueueExecutionResult result)
    {
        return new
        {
            total = result.TaskResults.Count,
            succeeded = result.TaskResults.Count(item => item.Status == JobStatus.Success),
            skipped = result.TaskResults.Count(item => item.Status == JobStatus.Skipped),
            failed = result.TaskResults.Count(item => item.Status == JobStatus.Failed),
            cancelled = result.TaskResults.Count(item => item.Status == JobStatus.Cancelled)
        };
    }

    private static async Task<TranscodeQueueExecutionResult> ExecuteTranscodeQueueAsync(
        ServiceContainer services,
        IReadOnlyList<TranscodeTaskSpec> tasks,
        IProgress<WorkflowProgress>? progress,
        Action<string>? logCallback,
        CancellationToken cancellationToken)
    {
        if (tasks.Count == 0)
        {
            throw new ArgumentException("转码任务列表不能为空。");
        }

        var presetNames = tasks
            .Select(task => string.IsNullOrWhiteSpace(task.Preset) ? "default" : task.Preset)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();

        if (presetNames.Count != 1)
        {
            throw new ArgumentException("当前 CLI 仅支持单一预设队列，请为所有任务使用同一个 preset。");
        }

        var settings = CreateSettingsForPreset(presetNames[0]);
        var hardware = await services.HardwareDetectionService.DetectAsync(cancellationToken);

        return await services.TranscodeQueueWorkflow.ExecuteAsync(
            tasks,
            settings,
            hardware.IsNvencAvailable,
            PrepareOverlayAsync,
            onTaskCompletedAsync: null,
            progress,
            logCallback,
            cancellationToken);
    }

    private static Task<TranscodeOverlayPreparationResult> PrepareOverlayAsync(
        TranscodeTaskSpec task,
        MediaProbeResult probe,
        Action<string>? logCallback,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        logCallback?.Invoke($"CLI 转码当前不注入 overlay，直接透传原始画面：{task.FileName}");
        return Task.FromResult(TranscodeOverlayPreparationResult.SuccessState(
            subtitleStreamOrdinal: null,
            danmakuAssPath: string.Empty,
            danmakuXmlPath: string.Empty,
            danmakuXmlCommentCount: 0,
            danmakuKeptCommentCount: 0,
            subtitleAnalysisSource: string.Empty,
            subtitleKindSummary: "CLI 未注入字幕叠加",
            danmakuSourceSummary: "CLI 未注入弹幕叠加",
            danmakuPreparationSummary: "CLI 未注入 overlay"));
    }

    private static async Task<IReadOnlyList<TranscodeTaskSpec>> LoadTranscodeTasksAsync(string specPath, CancellationToken cancellationToken)
    {
        var absolutePath = Path.GetFullPath(specPath);
        if (!File.Exists(absolutePath))
        {
            throw new ArgumentException($"spec.json 文件不存在：{absolutePath}");
        }

        var json = await File.ReadAllTextAsync(absolutePath, cancellationToken);
        TranscodeQueueSpecDocument? document;
        try
        {
            document = JsonSerializer.Deserialize<TranscodeQueueSpecDocument>(json, JsonOptions);
        }
        catch (JsonException ex)
        {
            throw new InvalidOperationException("spec.json 解析失败：JSON 格式无效。", ex);
        }

        if (document?.Tasks is null || document.Tasks.Count == 0)
        {
            throw new ArgumentException("spec.json 中缺少 tasks。");
        }

        var tasks = document.Tasks.Select(task =>
        {
            if (string.IsNullOrWhiteSpace(task.InputPath))
            {
                throw new ArgumentException("spec.json 中存在缺少 input 的任务。");
            }

            if (string.IsNullOrWhiteSpace(task.OutputPath))
            {
                throw new ArgumentException("spec.json 中存在缺少 output 的任务。");
            }

            return new TranscodeTaskSpec
            {
                TaskId = task.TaskId == Guid.Empty ? Guid.NewGuid() : task.TaskId,
                InputPath = task.InputPath,
                OutputPath = task.OutputPath,
                Preset = string.IsNullOrWhiteSpace(task.Preset) ? "default" : task.Preset,
                DeleteSource = task.DeleteSource,
                NoOverlay = task.NoOverlay
            };
        }).ToList();

        _ = CreateSettingsForPreset(tasks[0].Preset);
        return tasks;
    }

    private static WhisperOptions ResolveWhisperOptions(IReadOnlyDictionary<string, string?> options, string projectPath)
    {
        var config = LoadWhisperConfig(projectPath);
        var executablePath = FirstNonEmpty(
            GetOptionalString(options, "whisper-exe"),
            config.ExecutablePath,
            Environment.GetEnvironmentVariable("WHISPER_EXE_PATH"));
        var modelPath = FirstNonEmpty(
            GetOptionalString(options, "model"),
            config.ModelPath,
            Environment.GetEnvironmentVariable("WHISPER_MODEL_PATH"));

        if (string.IsNullOrWhiteSpace(executablePath) || string.IsNullOrWhiteSpace(modelPath))
        {
            throw new ArgumentException("whisper not configured: 需要通过 CLI、whisper-config.json 或环境变量提供 whisper 可执行文件和模型路径。");
        }

        return new WhisperOptions
        {
            ExecutablePath = executablePath,
            ModelPath = modelPath,
            Language = FirstNonEmpty(
                GetOptionalString(options, "language"),
                config.Language,
                Environment.GetEnvironmentVariable("WHISPER_LANGUAGE"),
                "auto")!,
            Threads = GetOptionalInt(options, "threads")
                ?? config.Threads
                ?? GetOptionalInt(Environment.GetEnvironmentVariable("WHISPER_THREADS"))
                ?? 0,
            ExtraArgs = FirstNonEmpty(
                GetOptionalString(options, "extra-args"),
                config.ExtraArgs,
                Environment.GetEnvironmentVariable("WHISPER_EXTRA_ARGS"),
                string.Empty) ?? string.Empty
        };
    }

    private static string ResolveProjectPathArgument(string projectArgument)
    {
        var absolutePath = Path.GetFullPath(projectArgument);
        if (File.Exists(absolutePath))
        {
            return absolutePath;
        }

        if (!Directory.Exists(absolutePath))
        {
            throw new ArgumentException($"项目路径不存在：{absolutePath}");
        }

        var projectFiles = Directory.GetFiles(absolutePath, "*.atproj", SearchOption.TopDirectoryOnly);
        if (projectFiles.Length == 1)
        {
            return projectFiles[0];
        }

        if (projectFiles.Length == 0)
        {
            throw new ArgumentException($"项目目录中未找到 .atproj 文件：{absolutePath}");
        }

        throw new ArgumentException($"项目目录中存在多个 .atproj 文件，无法确定要使用哪个：{absolutePath}");
    }

    private static WhisperConfigFile LoadWhisperConfig(string projectPath)
    {
        var projectDirectory = Path.GetDirectoryName(Path.GetFullPath(projectPath)) ?? Environment.CurrentDirectory;
        var candidatePaths = new[]
        {
            Path.Combine(projectDirectory, "whisper-config.json"),
            Path.Combine(Environment.CurrentDirectory, "whisper-config.json")
        }.Distinct(StringComparer.OrdinalIgnoreCase);

        foreach (var candidatePath in candidatePaths)
        {
            if (!File.Exists(candidatePath))
            {
                continue;
            }

            try
            {
                var json = File.ReadAllText(candidatePath);
                var config = JsonSerializer.Deserialize<WhisperConfigFile>(json, JsonOptions);
                if (config is not null)
                {
                    return config;
                }
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException($"读取 whisper-config.json 失败：{candidatePath} | {ex.Message}", ex);
            }
        }

        return new WhisperConfigFile();
    }

    private static AppSettings CreateSettingsForPreset(string presetName)
    {
        if (!string.Equals(presetName, "default", StringComparison.OrdinalIgnoreCase))
        {
            throw new ArgumentException($"未知 preset：{presetName}");
        }

        var settings = AppSettings.CreateDefault(Environment.CurrentDirectory);
        settings.OverwriteExisting = false;
        settings.DeleteSourceAfterSuccess = false;
        settings.EnableDanmaku = false;
        settings.BurnEmbeddedSubtitles = false;
        return settings;
    }

    private static string? FirstNonEmpty(params string?[] values)
    {
        return values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value));
    }

    private static void WriteJson<T>(T payload)
    {
        Console.Out.WriteLine(JsonSerializer.Serialize(payload, JsonOptions));
    }

    private static void PrintHelp()
    {
        Console.WriteLine("""
AnimeTranscoder.Cli

Commands:
  probe --input <path>
  audio extract --input <path> --output <path> [--track <n>] [--format AAC|MP3|WAV|FLAC|Copy] [--start <hh:mm:ss|seconds>] [--duration <...>] [--normalize true|false] [--bitrate 192] [--progress jsonl]
  audio detect-silence --input <path> [--track <n>] [--threshold -30] [--min-duration 2]
  project init --input <path> --project <path.atproj>
  project show --project <path.atproj>
  audio export-work --project <path.atproj> [--track <n>] [--sample-rate 16000] [--progress jsonl]
  transcript import --project <path.atproj> --input <transcript.json>
  transcript generate --project <project-dir> [--whisper-exe <path>] [--model <path>] [--language ja] [--threads 4] [--extra-args "..."] [--progress jsonl]
  selection import --project <path.atproj> --input <selection.json>
  audio render-selection --project <path.atproj> --output <path> [--mode PreserveTimeline|Concat] [--progress jsonl]
  transcode run --input <path> --output <path> [--preset default] [--no-overlay] [--progress jsonl]
  transcode queue --spec <spec.json> [--progress jsonl]

Whisper config priority:
  CLI flags > whisper-config.json > environment variables
  Env vars: WHISPER_EXE_PATH, WHISPER_MODEL_PATH, WHISPER_LANGUAGE, WHISPER_THREADS, WHISPER_EXTRA_ARGS
""");
    }

    private sealed class ServiceContainer
    {
        public required FfprobeService FfprobeService { get; init; }
        public required AudioExtractionService AudioExtractionService { get; init; }
        public required AudioProcessingWorkflow AudioProcessingWorkflow { get; init; }
        public required ProjectFileService ProjectFileService { get; init; }
        public required TranscriptDocumentService TranscriptDocumentService { get; init; }
        public required MediaProbeWorkflow MediaProbeWorkflow { get; init; }
        public required HardwareDetectionService HardwareDetectionService { get; init; }
        public required ProjectAudioWorkflow ProjectAudioWorkflow { get; init; }
        public required TranscodeQueueWorkflow TranscodeQueueWorkflow { get; init; }
    }

    private sealed class WhisperConfigFile
    {
        public string ExecutablePath { get; init; } = string.Empty;
        public string ModelPath { get; init; } = string.Empty;
        public string Language { get; init; } = string.Empty;
        public int? Threads { get; init; }
        public string ExtraArgs { get; init; } = string.Empty;
    }

    private sealed class TranscodeQueueSpecDocument
    {
        [JsonPropertyName("tasks")]
        public List<TranscodeQueueSpecTask> Tasks { get; init; } = [];
    }

    private sealed class TranscodeQueueSpecTask
    {
        [JsonPropertyName("input")]
        public string InputPath { get; init; } = string.Empty;

        [JsonPropertyName("output")]
        public string OutputPath { get; init; } = string.Empty;

        [JsonPropertyName("preset")]
        public string Preset { get; init; } = string.Empty;

        [JsonPropertyName("deleteSource")]
        public bool? DeleteSource { get; init; }

        [JsonPropertyName("noOverlay")]
        public bool NoOverlay { get; init; }

        [JsonPropertyName("taskId")]
        public Guid TaskId { get; init; }
    }
}
