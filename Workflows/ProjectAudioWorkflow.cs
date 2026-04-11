using AnimeTranscoder.Models;
using AnimeTranscoder.Services;

namespace AnimeTranscoder.Workflows;

public sealed class ProjectAudioWorkflowDependencies
{
    public required Func<string, CancellationToken, Task<AnimeProjectFile>> LoadProjectAsync { get; init; }
    public required Func<string, AnimeProjectFile, CancellationToken, Task> SaveProjectAsync { get; init; }
    public required Func<string, CancellationToken, Task<TranscriptDocument>> LoadTranscriptAsync { get; init; }
    public required Func<string, TranscriptDocument, CancellationToken, Task> SaveTranscriptAsync { get; init; }
    public required Func<string, CancellationToken, Task<SelectionDocument>> LoadSelectionAsync { get; init; }
    public required Func<string, string, int?, int, Action<double, string>?, CancellationToken, Task<AudioExtractionResult>> ExtractWorkAudioAsync { get; init; }
    public required Func<string, string, TranscriptDocument, SelectionDocument, AudioRenderMode, Action<double, string>?, CancellationToken, Task<AudioExtractionResult>> RenderSelectionAsync { get; init; }
    public required Func<string, CancellationToken, Task<MediaProbeResult?>> ProbeMediaAsync { get; init; }
    public Func<string, WhisperOptions, IProgress<double>?, CancellationToken, Task<TranscriptDocument>>? TranscribeAsync { get; init; }
}

public sealed class ProjectAudioWorkflow
{
    private readonly ProjectAudioWorkflowDependencies _dependencies;
    private readonly ProjectFileService? _projectFileService;

    public ProjectAudioWorkflow(
        ProjectFileService projectFileService,
        TranscriptDocumentService transcriptDocumentService,
        SelectionDocumentService selectionDocumentService,
        AudioExtractionService audioExtractionService,
        AudioSelectionRenderService audioSelectionRenderService,
        FfprobeService ffprobeService,
        ITranscriptionService? transcriptionService = null)
        : this(
            new ProjectAudioWorkflowDependencies
            {
                LoadProjectAsync = projectFileService.LoadAsync,
                SaveProjectAsync = projectFileService.SaveAsync,
                LoadTranscriptAsync = transcriptDocumentService.LoadAsync,
                SaveTranscriptAsync = transcriptDocumentService.SaveAsync,
                LoadSelectionAsync = selectionDocumentService.LoadAsync,
                ExtractWorkAudioAsync = audioExtractionService.ExtractWorkAudioAsync,
                RenderSelectionAsync = audioSelectionRenderService.RenderAsync,
                ProbeMediaAsync = ffprobeService.ProbeAsync,
                TranscribeAsync = transcriptionService is null
                    ? null
                    : (audioFilePath, options, progress, cancellationToken) =>
                        transcriptionService.TranscribeAsync(audioFilePath, options, progress, cancellationToken)
            },
            projectFileService)
    {
    }

    public ProjectAudioWorkflow(ProjectAudioWorkflowDependencies dependencies, ProjectFileService? projectFileService = null)
    {
        _dependencies = dependencies;
        _projectFileService = projectFileService;
    }

    public async Task<AnimeProjectFile> InitializeAsync(string inputPath, string projectPath, CancellationToken cancellationToken)
    {
        var projectService = _projectFileService ?? throw new InvalidOperationException("初始化项目需要 ProjectFileService。");
        var project = projectService.Create(inputPath, projectPath);
        await _dependencies.SaveProjectAsync(projectPath, project, cancellationToken);
        return project;
    }

    public async Task<AudioExtractionResult> ExportWorkAudioAsync(
        string projectPath,
        int? trackIndex,
        int sampleRate,
        IProgress<WorkflowProgress>? progress,
        CancellationToken cancellationToken)
    {
        var project = await _dependencies.LoadProjectAsync(projectPath, cancellationToken);
        var outputPath = Path.Combine(project.WorkingDirectory, "work-audio.wav");
        if (!File.Exists(project.InputPath))
        {
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "输入文件不存在"
            };
        }

        var probe = await _dependencies.ProbeMediaAsync(project.InputPath, cancellationToken)
            ?? throw new InvalidOperationException("媒体探测失败。");
        if (probe.AudioTracks.Count == 0)
        {
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "输入媒体没有音轨"
            };
        }

        var effectiveTrackIndex = trackIndex ?? project.SelectedAudioTrackIndex;
        if (effectiveTrackIndex.HasValue && probe.AudioTracks.All(item => item.Index != effectiveTrackIndex.Value))
        {
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = $"音轨索引无效：{effectiveTrackIndex.Value}"
            };
        }

        var result = await _dependencies.ExtractWorkAudioAsync(
            project.InputPath,
            outputPath,
            effectiveTrackIndex,
            sampleRate,
            (progressValue, speed) => ReportProgress(progress, "audio.export-work", progressValue, speed, "正在导出工作音频"),
            cancellationToken);

        if (result.Success)
        {
            project.WorkingAudioPath = outputPath;
            project.SelectedAudioTrackIndex = effectiveTrackIndex;
            project.Status = "work_audio_exported";
            await _dependencies.SaveProjectAsync(projectPath, project, cancellationToken);
            ReportProgress(progress, "audio.export-work", 100d, "done", "工作音频导出完成");
        }

        return result;
    }

    public async Task<AnimeProjectFile> ImportTranscriptAsync(string projectPath, string transcriptPath, CancellationToken cancellationToken)
    {
        var project = await _dependencies.LoadProjectAsync(projectPath, cancellationToken);
        _ = await _dependencies.LoadTranscriptAsync(transcriptPath, cancellationToken);
        project.TranscriptPath = Path.GetFullPath(transcriptPath);
        project.Status = "transcript_imported";
        await _dependencies.SaveProjectAsync(projectPath, project, cancellationToken);
        return project;
    }

    public async Task<AnimeProjectFile> ImportSelectionAsync(string projectPath, string selectionPath, CancellationToken cancellationToken)
    {
        var project = await _dependencies.LoadProjectAsync(projectPath, cancellationToken);
        _ = await _dependencies.LoadSelectionAsync(selectionPath, cancellationToken);
        project.SelectionPath = Path.GetFullPath(selectionPath);
        project.Status = "selection_imported";
        await _dependencies.SaveProjectAsync(projectPath, project, cancellationToken);
        return project;
    }

    public async Task<AnimeProjectFile> GenerateTranscriptAsync(
        string projectPath,
        WhisperOptions options,
        IProgress<double>? progress,
        CancellationToken cancellationToken)
    {
        if (_dependencies.TranscribeAsync is null)
        {
            throw new InvalidOperationException("当前 workflow 未配置转录服务。");
        }

        var project = await _dependencies.LoadProjectAsync(projectPath, cancellationToken);
        if (string.IsNullOrWhiteSpace(project.WorkingAudioPath))
        {
            throw new InvalidOperationException("项目中缺少工作音频路径，请先执行 export-work。");
        }

        if (!File.Exists(project.WorkingAudioPath))
        {
            throw new FileNotFoundException("工作音频文件不存在。", project.WorkingAudioPath);
        }

        if (new FileInfo(project.WorkingAudioPath).Length == 0)
        {
            throw new InvalidOperationException("工作音频文件为空。");
        }

        var transcript = await _dependencies.TranscribeAsync(project.WorkingAudioPath, options, progress, cancellationToken);
        var projectDirectory = Path.GetDirectoryName(Path.GetFullPath(projectPath))
            ?? throw new InvalidOperationException("项目目录无效。");
        Directory.CreateDirectory(projectDirectory);
        var transcriptPath = Path.Combine(projectDirectory, "transcript.json");
        await _dependencies.SaveTranscriptAsync(transcriptPath, transcript, cancellationToken);
        project.TranscriptPath = transcriptPath;
        project.Status = "transcript_generated";
        await _dependencies.SaveProjectAsync(projectPath, project, cancellationToken);
        return project;
    }

    public async Task<AudioExtractionResult> RenderSelectionAsync(
        string projectPath,
        string outputPath,
        AudioRenderMode mode,
        IProgress<WorkflowProgress>? progress,
        CancellationToken cancellationToken)
    {
        var project = await _dependencies.LoadProjectAsync(projectPath, cancellationToken);
        if (string.IsNullOrWhiteSpace(project.WorkingAudioPath))
        {
            throw new InvalidOperationException("项目中缺少工作音频路径，请先执行 export-work。");
        }

        if (string.IsNullOrWhiteSpace(project.TranscriptPath))
        {
            throw new InvalidOperationException("项目中缺少 transcript 路径，请先导入 transcript。");
        }

        if (string.IsNullOrWhiteSpace(project.SelectionPath))
        {
            throw new InvalidOperationException("项目中缺少 selection 路径，请先导入 selection。");
        }

        if (!File.Exists(project.WorkingAudioPath))
        {
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "工作音频文件不存在"
            };
        }

        if (new FileInfo(project.WorkingAudioPath).Length == 0)
        {
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "工作音频文件为空"
            };
        }

        var transcript = await _dependencies.LoadTranscriptAsync(project.TranscriptPath, cancellationToken);
        var selection = await _dependencies.LoadSelectionAsync(project.SelectionPath, cancellationToken);
        var outputDirectory = Path.GetDirectoryName(Path.GetFullPath(outputPath));
        if (!string.IsNullOrWhiteSpace(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        var result = await _dependencies.RenderSelectionAsync(
            project.WorkingAudioPath,
            outputPath,
            transcript,
            selection,
            mode,
            (progressValue, speed) => ReportProgress(progress, "audio.render-selection", progressValue, speed, "正在按选择结果渲染音频"),
            cancellationToken);

        if (result.Success)
        {
            project.Status = "selection_rendered";
            await _dependencies.SaveProjectAsync(projectPath, project, cancellationToken);
            ReportProgress(progress, "audio.render-selection", 100d, "done", "按选择结果渲染完成");
        }

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
