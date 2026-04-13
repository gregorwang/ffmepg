using System.Text.Json;
using System.Text.Json.Serialization;
using System.Windows.Input;
using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;
using AnimeTranscoder.Services;
using AnimeTranscoder.Workflows;

namespace AnimeTranscoder.ViewModels;

public sealed partial class MainViewModel
{
    private readonly ProjectFileService _projectFileService;
    private readonly TranscriptDocumentService _transcriptDocumentService;
    private readonly SelectionDocumentService _selectionDocumentService;
    private readonly ProjectAudioWorkflow _projectAudioWorkflow;
    private readonly AudioProcessingWorkflow _audioProcessingWorkflow;
    private static readonly JsonSerializerOptions WhisperConfigJsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
        Converters = { new JsonStringEnumConverter() }
    };

    private CancellationTokenSource? _transcriptGenerationCancellationTokenSource;
    private string _audioProjectPath = string.Empty;
    private string _audioProjectStatusSummary = "尚未创建或加载音频项目";
    private string _audioProjectWorkingAudioPath = string.Empty;
    private string _audioProjectTranscriptPath = string.Empty;
    private string _audioProjectSelectionPath = string.Empty;
    private AnimeProjectFile? _loadedAudioProject;
    private AudioRenderMode _selectedAudioRenderMode = AudioRenderMode.PreserveTimeline;
    private string _whisperExePath = string.Empty;
    private string _whisperModelPath = string.Empty;
    private string _whisperLanguage = "auto";
    private string _whisperThreadsText = "4";
    private string _whisperExtraArgs = string.Empty;
    private bool _isTranscriptGenerating;
    private double _transcriptGenerationProgress;
    private string _transcriptGenerationStatusMessage = string.Empty;

    public ICommand CreateAudioProjectCommand { get; private set; } = null!;
    public ICommand LoadAudioProjectCommand { get; private set; } = null!;
    public ICommand ExportAudioWorkCommand { get; private set; } = null!;
    public ICommand ImportAudioTranscriptCommand { get; private set; } = null!;
    public ICommand ImportAudioSelectionCommand { get; private set; } = null!;
    public ICommand RenderAudioSelectionCommand { get; private set; } = null!;
    public ICommand OpenAudioProjectDirectoryCommand { get; private set; } = null!;
    public ICommand GenerateTranscriptCommand { get; private set; } = null!;
    public ICommand CancelTranscriptGenerationCommand { get; private set; } = null!;
    public ICommand ChooseWhisperExeCommand { get; private set; } = null!;
    public ICommand ChooseWhisperModelCommand { get; private set; } = null!;

    public string AudioProjectPath
    {
        get => _audioProjectPath;
        private set => SetProperty(ref _audioProjectPath, value);
    }

    public string AudioProjectStatusSummary
    {
        get => _audioProjectStatusSummary;
        private set => SetProperty(ref _audioProjectStatusSummary, value);
    }

    public string AudioProjectWorkingAudioPath
    {
        get => _audioProjectWorkingAudioPath;
        private set => SetProperty(ref _audioProjectWorkingAudioPath, value);
    }

    public string AudioProjectTranscriptPath
    {
        get => _audioProjectTranscriptPath;
        private set => SetProperty(ref _audioProjectTranscriptPath, value);
    }

    public string AudioProjectSelectionPath
    {
        get => _audioProjectSelectionPath;
        private set => SetProperty(ref _audioProjectSelectionPath, value);
    }

    public bool HasLoadedAudioProject => _loadedAudioProject is not null && !string.IsNullOrWhiteSpace(AudioProjectPath);

    public bool IsAudioProjectAligned =>
        _loadedAudioProject is not null &&
        !string.IsNullOrWhiteSpace(AudioInputPath) &&
        string.Equals(Path.GetFullPath(AudioInputPath), _loadedAudioProject.InputPath, StringComparison.OrdinalIgnoreCase);

    public AudioRenderMode SelectedAudioRenderMode
    {
        get => _selectedAudioRenderMode;
        set => SetProperty(ref _selectedAudioRenderMode, value);
    }

    public string WhisperExePath
    {
        get => _whisperExePath;
        set => SetProperty(ref _whisperExePath, value);
    }

    public string WhisperModelPath
    {
        get => _whisperModelPath;
        set => SetProperty(ref _whisperModelPath, value);
    }

    public string WhisperLanguage
    {
        get => _whisperLanguage;
        set => SetProperty(ref _whisperLanguage, value);
    }

    public string WhisperThreadsText
    {
        get => _whisperThreadsText;
        set => SetProperty(ref _whisperThreadsText, value);
    }

    public string WhisperExtraArgs
    {
        get => _whisperExtraArgs;
        set => SetProperty(ref _whisperExtraArgs, value);
    }

    public bool IsTranscriptGenerating
    {
        get => _isTranscriptGenerating;
        private set
        {
            if (SetProperty(ref _isTranscriptGenerating, value))
            {
                NotifyCommandStateChanged();
                NotifyAudioProjectCommandStateChanged();
            }
        }
    }

    public double TranscriptGenerationProgress
    {
        get => _transcriptGenerationProgress;
        private set
        {
            if (SetProperty(ref _transcriptGenerationProgress, value))
            {
                RaisePropertyChanged(nameof(TranscriptGenerationProgressText));
            }
        }
    }

    public string TranscriptGenerationProgressText => $"{TranscriptGenerationProgress:F0}%";

    public string TranscriptGenerationStatusMessage
    {
        get => _transcriptGenerationStatusMessage;
        private set => SetProperty(ref _transcriptGenerationStatusMessage, value);
    }

    private void InitializeAudioProjectFeature()
    {
        CreateAudioProjectCommand = new AsyncRelayCommand(CreateAudioProjectAsync, CanCreateAudioProject);
        LoadAudioProjectCommand = new AsyncRelayCommand(LoadAudioProjectAsync, CanLoadAudioProject);
        ExportAudioWorkCommand = new AsyncRelayCommand(ExportAudioWorkAsync, CanExportAudioWork);
        ImportAudioTranscriptCommand = new AsyncRelayCommand(ImportAudioTranscriptAsync, CanImportAudioTranscript);
        ImportAudioSelectionCommand = new AsyncRelayCommand(ImportAudioSelectionAsync, CanImportAudioSelection);
        RenderAudioSelectionCommand = new AsyncRelayCommand(RenderAudioSelectionAsync, CanRenderAudioSelection);
        OpenAudioProjectDirectoryCommand = new RelayCommand(_ => OpenAudioProjectDirectory(), _ => _loadedAudioProject is not null && Directory.Exists(_loadedAudioProject.WorkingDirectory));
        GenerateTranscriptCommand = new AsyncRelayCommand(GenerateTranscriptAsync, CanGenerateTranscript);
        CancelTranscriptGenerationCommand = new RelayCommand(_ => CancelTranscriptGeneration(), _ => IsTranscriptGenerating);
        ChooseWhisperExeCommand = new RelayCommand(_ => ChooseWhisperExe(), _ => !IsTranscriptGenerating);
        ChooseWhisperModelCommand = new RelayCommand(_ => ChooseWhisperModel(), _ => !IsTranscriptGenerating);
        LoadWhisperConfig();
    }

    private void NotifyAudioProjectCommandStateChanged()
    {
        RaisePropertyChanged(nameof(HasLoadedAudioProject));
        RaisePropertyChanged(nameof(IsAudioProjectAligned));

        if (CreateAudioProjectCommand is AsyncRelayCommand create)
        {
            create.NotifyCanExecuteChanged();
        }

        if (LoadAudioProjectCommand is AsyncRelayCommand load)
        {
            load.NotifyCanExecuteChanged();
        }

        if (ExportAudioWorkCommand is AsyncRelayCommand exportWork)
        {
            exportWork.NotifyCanExecuteChanged();
        }

        if (ImportAudioTranscriptCommand is AsyncRelayCommand importTranscript)
        {
            importTranscript.NotifyCanExecuteChanged();
        }

        if (ImportAudioSelectionCommand is AsyncRelayCommand importSelection)
        {
            importSelection.NotifyCanExecuteChanged();
        }

        if (RenderAudioSelectionCommand is AsyncRelayCommand renderSelection)
        {
            renderSelection.NotifyCanExecuteChanged();
        }

        if (OpenAudioProjectDirectoryCommand is RelayCommand openProjectDirectory)
        {
            openProjectDirectory.NotifyCanExecuteChanged();
        }

        if (GenerateTranscriptCommand is AsyncRelayCommand generate)
        {
            generate.NotifyCanExecuteChanged();
        }

        if (CancelTranscriptGenerationCommand is RelayCommand cancelGenerate)
        {
            cancelGenerate.NotifyCanExecuteChanged();
        }

        if (ChooseWhisperExeCommand is RelayCommand chooseExe)
        {
            chooseExe.NotifyCanExecuteChanged();
        }

        if (ChooseWhisperModelCommand is RelayCommand chooseModel)
        {
            chooseModel.NotifyCanExecuteChanged();
        }
    }

    private void OnAudioSourceLoaded(string inputPath)
    {
        if (_loadedAudioProject is null)
        {
            return;
        }

        var aligned = string.Equals(Path.GetFullPath(inputPath), _loadedAudioProject.InputPath, StringComparison.OrdinalIgnoreCase);
        AudioProjectStatusSummary = aligned
            ? BuildAudioProjectStatusSummary(_loadedAudioProject, $"已对齐当前音频源 | 状态 {_loadedAudioProject.Status}")
            : BuildAudioProjectStatusSummary(_loadedAudioProject, "当前音频源与已加载项目不一致，项目操作已暂停");
        NotifyAudioProjectCommandStateChanged();
    }

    private bool CanCreateAudioProject()
    {
        return !IsRunning
            && !IsAudioExtracting
            && !IsAudioSilenceDetecting
            && !IsClipRunning
            && !IsDouyinExporting
            && !string.IsNullOrWhiteSpace(AudioInputPath)
            && File.Exists(AudioInputPath);
    }

    private bool CanLoadAudioProject()
    {
        return !IsRunning
            && !IsAudioExtracting
            && !IsAudioSilenceDetecting
            && !IsClipRunning
            && !IsDouyinExporting;
    }

    private bool CanExportAudioWork()
    {
        return CanLoadAudioProject()
            && HasLoadedAudioProject
            && IsAudioProjectAligned
            && SelectedAudioTrack is not null;
    }

    private bool CanImportAudioTranscript()
    {
        return CanLoadAudioProject()
            && HasLoadedAudioProject;
    }

    private bool CanImportAudioSelection()
    {
        return CanLoadAudioProject()
            && HasLoadedAudioProject;
    }

    private bool CanRenderAudioSelection()
    {
        return CanLoadAudioProject()
            && HasLoadedAudioProject
            && IsAudioProjectAligned
            && !string.IsNullOrWhiteSpace(AudioProjectWorkingAudioPath)
            && File.Exists(AudioProjectWorkingAudioPath)
            && !string.IsNullOrWhiteSpace(AudioProjectTranscriptPath)
            && File.Exists(AudioProjectTranscriptPath)
            && !string.IsNullOrWhiteSpace(AudioProjectSelectionPath)
            && File.Exists(AudioProjectSelectionPath);
    }

    private async Task CreateAudioProjectAsync()
    {
        if (!CanCreateAudioProject())
        {
            return;
        }

        var defaultName = $"{Path.GetFileNameWithoutExtension(AudioInputPath)}.atproj";
        var initialDirectory = Path.GetDirectoryName(AudioInputPath) ?? Settings.OutputDirectory;
        var projectPath = _userDialogService.PickSaveFile(
            "创建音频项目",
            "AnimeTranscoder 项目 (*.atproj)|*.atproj|JSON 文件 (*.json)|*.json",
            defaultName,
            initialDirectory);
        if (string.IsNullOrWhiteSpace(projectPath))
        {
            return;
        }

        var project = await _projectAudioWorkflow.InitializeAsync(AudioInputPath, projectPath, CancellationToken.None);
        ApplyLoadedAudioProject(projectPath, project, "音频项目已创建");
        AppendLog($"已创建音频项目：{projectPath}");
        StatusMessage = "音频项目已创建";
    }

    private async Task LoadAudioProjectAsync()
    {
        if (!CanLoadAudioProject())
        {
            return;
        }

        var projectPath = _userDialogService.PickFile(
            "加载音频项目",
            "AnimeTranscoder 项目 (*.atproj;*.json)|*.atproj;*.json|所有文件 (*.*)|*.*",
            Settings.OutputDirectory);
        if (string.IsNullOrWhiteSpace(projectPath))
        {
            return;
        }

        var project = await _projectFileService.LoadAsync(projectPath);
        ApplyLoadedAudioProject(projectPath, project, "音频项目已加载");
        if (!string.Equals(AudioInputPath, project.InputPath, StringComparison.OrdinalIgnoreCase))
        {
            await LoadAudioSourceAsync(project.InputPath, "音频项目");
        }

        ApplySelectedAudioTrackFromProject(project);
        AudioProjectStatusSummary = BuildAudioProjectStatusSummary(project, "音频项目已加载");
        AppendLog($"已加载音频项目：{projectPath}");
        StatusMessage = "音频项目已加载";
        NotifyAudioProjectCommandStateChanged();
    }

    private async Task ExportAudioWorkAsync()
    {
        if (!CanExportAudioWork())
        {
            return;
        }

        AudioProgress = 0;
        AudioSpeed = string.Empty;
        AudioStatusMessage = "正在导出工作音频";
        StatusMessage = "正在导出工作音频";
        IsAudioExtracting = true;
        _audioExtractionCancellationTokenSource = new CancellationTokenSource();

        try
        {
            var result = await _projectAudioWorkflow.ExportWorkAudioAsync(
                AudioProjectPath,
                SelectedAudioTrack?.Index,
                16000,
                new Progress<WorkflowProgress>(OnAudioWorkflowProgress),
                _audioExtractionCancellationTokenSource.Token);

            if (!result.Success)
            {
                AudioStatusMessage = $"工作音频导出失败：{result.ErrorMessage}";
                StatusMessage = "工作音频导出失败";
                AppendLog($"工作音频导出失败：{result.ErrorMessage}");
                return;
            }

            await ReloadCurrentAudioProjectAsync("工作音频已导出");
            AudioProgress = 100;
            AudioSpeed = "done";
            AudioStatusMessage = "工作音频导出完成";
            StatusMessage = "工作音频导出完成";
            AppendLog($"工作音频导出完成：{AudioProjectWorkingAudioPath}");
        }
        finally
        {
            IsAudioExtracting = false;
            _audioExtractionCancellationTokenSource?.Dispose();
            _audioExtractionCancellationTokenSource = null;
            NotifyCommandStateChanged();
        }
    }

    private async Task ImportAudioTranscriptAsync()
    {
        if (!CanImportAudioTranscript())
        {
            return;
        }

        var initialDirectory = _loadedAudioProject is not null
            ? _loadedAudioProject.WorkingDirectory
            : Settings.OutputDirectory;
        var path = _userDialogService.PickFile(
            "导入 Transcript",
            "JSON 文件 (*.json)|*.json|所有文件 (*.*)|*.*",
            initialDirectory);
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        var document = await _transcriptDocumentService.LoadAsync(path);
        await _projectAudioWorkflow.ImportTranscriptAsync(AudioProjectPath, path, CancellationToken.None);
        await ReloadCurrentAudioProjectAsync($"已导入 transcript，共 {document.Segments.Count} 条 segment");
        StatusMessage = "Transcript 已导入";
        AppendLog($"已导入 transcript：{path} | 条数 {document.Segments.Count}");
    }

    private async Task ImportAudioSelectionAsync()
    {
        if (!CanImportAudioSelection())
        {
            return;
        }

        var initialDirectory = _loadedAudioProject is not null
            ? _loadedAudioProject.WorkingDirectory
            : Settings.OutputDirectory;
        var path = _userDialogService.PickFile(
            "导入 Selection",
            "JSON 文件 (*.json)|*.json|所有文件 (*.*)|*.*",
            initialDirectory);
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        var document = await _selectionDocumentService.LoadAsync(path);
        await _projectAudioWorkflow.ImportSelectionAsync(AudioProjectPath, path, CancellationToken.None);
        await ReloadCurrentAudioProjectAsync($"已导入 selection，共 {document.TargetSegments.Count} 条决策");
        StatusMessage = "Selection 已导入";
        AppendLog($"已导入 selection：{path} | 条数 {document.TargetSegments.Count}");
    }

    private async Task RenderAudioSelectionAsync()
    {
        if (!CanRenderAudioSelection())
        {
            return;
        }

        var defaultName = $"{Path.GetFileNameWithoutExtension(AudioInputPath)}-{SelectedAudioRenderMode.ToString().ToLowerInvariant()}.wav";
        var outputPath = _userDialogService.PickSaveFile(
            "导出筛选音频",
            "WAV 文件 (*.wav)|*.wav|FLAC 文件 (*.flac)|*.flac|AAC 文件 (*.m4a)|*.m4a|MP3 文件 (*.mp3)|*.mp3",
            defaultName,
            _loadedAudioProject?.WorkingDirectory ?? Settings.OutputDirectory);
        if (string.IsNullOrWhiteSpace(outputPath))
        {
            return;
        }

        AudioProgress = 0;
        AudioSpeed = string.Empty;
        AudioStatusMessage = "正在按选择结果渲染音频";
        StatusMessage = "正在按选择结果渲染音频";
        IsAudioExtracting = true;
        _audioExtractionCancellationTokenSource = new CancellationTokenSource();

        try
        {
            var result = await _projectAudioWorkflow.RenderSelectionAsync(
                AudioProjectPath,
                outputPath,
                SelectedAudioRenderMode,
                new Progress<WorkflowProgress>(OnAudioWorkflowProgress),
                _audioExtractionCancellationTokenSource.Token);

            if (!result.Success)
            {
                AudioStatusMessage = $"筛选音频导出失败：{result.ErrorMessage}";
                StatusMessage = "筛选音频导出失败";
                AppendLog($"筛选音频导出失败：{result.ErrorMessage}");
                return;
            }

            await ReloadCurrentAudioProjectAsync("按选择结果渲染完成");
            AudioProgress = 100;
            AudioSpeed = "done";
            AudioStatusMessage = $"筛选音频已生成：{Path.GetFileName(outputPath)}";
            StatusMessage = "筛选音频已生成";
            AppendLog($"筛选音频已生成：{outputPath}");
        }
        finally
        {
            IsAudioExtracting = false;
            _audioExtractionCancellationTokenSource?.Dispose();
            _audioExtractionCancellationTokenSource = null;
            NotifyCommandStateChanged();
        }
    }

    private async Task ReloadCurrentAudioProjectAsync(string summary)
    {
        if (!HasLoadedAudioProject)
        {
            return;
        }

        var project = await _projectFileService.LoadAsync(AudioProjectPath);
        ApplyLoadedAudioProject(AudioProjectPath, project, summary);
        ApplySelectedAudioTrackFromProject(project);
    }

    private void ApplyLoadedAudioProject(string projectPath, AnimeProjectFile project, string summary)
    {
        _loadedAudioProject = project;
        AudioProjectPath = Path.GetFullPath(projectPath);
        AudioProjectWorkingAudioPath = project.WorkingAudioPath;
        AudioProjectTranscriptPath = project.TranscriptPath;
        AudioProjectSelectionPath = project.SelectionPath;
        AudioProjectStatusSummary = BuildAudioProjectStatusSummary(project, summary);
        NotifyAudioProjectCommandStateChanged();
    }

    private void ApplySelectedAudioTrackFromProject(AnimeProjectFile project)
    {
        if (!project.SelectedAudioTrackIndex.HasValue)
        {
            return;
        }

        var track = AudioTracks.FirstOrDefault(item => item.Index == project.SelectedAudioTrackIndex.Value);
        if (track is not null)
        {
            SelectedAudioTrack = track;
        }
    }

    private void OnAudioWorkflowProgress(WorkflowProgress progress)
    {
        AudioProgress = Math.Round(progress.ProgressPercent, 2);
        if (!string.IsNullOrWhiteSpace(progress.Speed) &&
            !string.Equals(progress.Speed, "done", StringComparison.OrdinalIgnoreCase))
        {
            AudioSpeed = progress.Speed;
        }

        if (!string.IsNullOrWhiteSpace(progress.Message))
        {
            AudioStatusMessage = progress.Message;
        }
    }

    private void OpenAudioProjectDirectory()
    {
        if (_loadedAudioProject is not null && Directory.Exists(_loadedAudioProject.WorkingDirectory))
        {
            _userDialogService.OpenFolder(_loadedAudioProject.WorkingDirectory);
        }
    }

    private static string BuildAudioProjectStatusSummary(AnimeProjectFile project, string prefix)
    {
        return $"{prefix} | 状态 {project.Status} | 工作目录 {project.WorkingDirectory}";
    }

    private bool CanGenerateTranscript()
    {
        return !IsRunning
            && !IsAudioExtracting
            && !IsAudioSilenceDetecting
            && !IsClipRunning
            && !IsDouyinExporting
            && !IsTranscriptGenerating
            && HasLoadedAudioProject
            && IsAudioProjectAligned
            && !string.IsNullOrWhiteSpace(AudioProjectWorkingAudioPath)
            && File.Exists(AudioProjectWorkingAudioPath)
            && !string.IsNullOrWhiteSpace(WhisperExePath)
            && !string.IsNullOrWhiteSpace(WhisperModelPath);
    }

    private async Task GenerateTranscriptAsync()
    {
        if (!CanGenerateTranscript())
        {
            return;
        }

        if (!int.TryParse(WhisperThreadsText, out var threads) || threads < 0)
        {
            threads = 0;
        }

        var options = new WhisperOptions
        {
            ExecutablePath = WhisperExePath,
            ModelPath = WhisperModelPath,
            Language = string.IsNullOrWhiteSpace(WhisperLanguage) ? "auto" : WhisperLanguage,
            Threads = threads,
            ExtraArgs = WhisperExtraArgs ?? string.Empty
        };

        TranscriptGenerationProgress = 0;
        TranscriptGenerationStatusMessage = "正在生成 Transcript...";
        AudioStatusMessage = "正在生成 Transcript (Whisper)";
        StatusMessage = "正在生成 Transcript";
        IsTranscriptGenerating = true;
        _transcriptGenerationCancellationTokenSource = new CancellationTokenSource();

        try
        {
            var progress = new Progress<double>(value =>
            {
                TranscriptGenerationProgress = Math.Round(value, 2);
                TranscriptGenerationStatusMessage = $"Whisper 识别中... {value:F0}%";
            });

            var project = await _projectAudioWorkflow.GenerateTranscriptAsync(
                AudioProjectPath,
                options,
                progress,
                _transcriptGenerationCancellationTokenSource.Token);

            var transcript = await _transcriptDocumentService.LoadAsync(project.TranscriptPath);
            await ReloadCurrentAudioProjectAsync($"Transcript 已生成，共 {transcript.Segments.Count} 条 segment");
            TranscriptGenerationProgress = 100;
            TranscriptGenerationStatusMessage = $"Transcript 生成完成！共 {transcript.Segments.Count} 条 segment";
            AudioStatusMessage = "Transcript 生成完成";
            StatusMessage = "Transcript 生成完成";
            AppendLog($"Transcript 生成完成：{project.TranscriptPath} | 条数 {transcript.Segments.Count}");
            SaveWhisperConfig();
        }
        catch (OperationCanceledException)
        {
            TranscriptGenerationStatusMessage = "Transcript 生成已取消";
            AudioStatusMessage = "Transcript 生成已取消";
            StatusMessage = "Transcript 生成已取消";
            AppendLog("Transcript 生成已取消。");
        }
        catch (Exception ex)
        {
            TranscriptGenerationStatusMessage = $"Transcript 生成失败：{ex.Message}";
            AudioStatusMessage = $"Transcript 生成失败：{ex.Message}";
            StatusMessage = "Transcript 生成失败";
            AppendLog($"Transcript 生成异常：{ex.Message}");
            AppFileLogger.Write("TranscriptGenerate", $"异常：{ex}");
        }
        finally
        {
            IsTranscriptGenerating = false;
            _transcriptGenerationCancellationTokenSource?.Dispose();
            _transcriptGenerationCancellationTokenSource = null;
            NotifyCommandStateChanged();
            NotifyAudioProjectCommandStateChanged();
        }
    }

    private void CancelTranscriptGeneration()
    {
        _transcriptGenerationCancellationTokenSource?.Cancel();
        TranscriptGenerationStatusMessage = "正在取消...";
    }

    private void ChooseWhisperExe()
    {
        var path = _userDialogService.PickFile(
            "选择 Whisper 可执行文件",
            "可执行文件 (*.exe)|*.exe|所有文件 (*.*)|*.*",
            string.IsNullOrWhiteSpace(WhisperExePath) ? Environment.CurrentDirectory : Path.GetDirectoryName(WhisperExePath) ?? Environment.CurrentDirectory);
        if (!string.IsNullOrWhiteSpace(path))
        {
            WhisperExePath = path;
            NotifyAudioProjectCommandStateChanged();
        }
    }

    private void ChooseWhisperModel()
    {
        var path = _userDialogService.PickFile(
            "选择 Whisper 模型文件",
            "GGML 模型 (*.bin)|*.bin|所有文件 (*.*)|*.*",
            string.IsNullOrWhiteSpace(WhisperModelPath) ? Environment.CurrentDirectory : Path.GetDirectoryName(WhisperModelPath) ?? Environment.CurrentDirectory);
        if (!string.IsNullOrWhiteSpace(path))
        {
            WhisperModelPath = path;
            NotifyAudioProjectCommandStateChanged();
        }
    }

    private void LoadWhisperConfig()
    {
        var configPaths = new[]
        {
            Path.Combine(Environment.CurrentDirectory, "whisper-config.json"),
            Path.Combine(ToolPathResolver.ResolveWorkspaceRoot(), "whisper-config.json")
        }.Distinct(StringComparer.OrdinalIgnoreCase);

        foreach (var configPath in configPaths)
        {
            if (!File.Exists(configPath))
            {
                continue;
            }

            try
            {
                var json = File.ReadAllText(configPath);
                var config = JsonSerializer.Deserialize<WhisperGuiConfigFile>(json, WhisperConfigJsonOptions);
                if (config is null)
                {
                    continue;
                }

                if (!string.IsNullOrWhiteSpace(config.ExecutablePath))
                {
                    WhisperExePath = config.ExecutablePath;
                }

                if (!string.IsNullOrWhiteSpace(config.ModelPath))
                {
                    WhisperModelPath = config.ModelPath;
                }

                if (!string.IsNullOrWhiteSpace(config.Language))
                {
                    WhisperLanguage = config.Language;
                }

                if (config.Threads.HasValue)
                {
                    WhisperThreadsText = config.Threads.Value.ToString();
                }

                if (!string.IsNullOrWhiteSpace(config.ExtraArgs))
                {
                    WhisperExtraArgs = config.ExtraArgs;
                }

                AppFileLogger.Write("WhisperConfig", $"已从 {configPath} 加载 Whisper 配置");
                return;
            }
            catch (Exception ex)
            {
                AppFileLogger.Write("WhisperConfig", $"读取 whisper-config.json 失败：{configPath} | {ex.Message}");
            }
        }

        // Fallback: environment variables
        var envExe = Environment.GetEnvironmentVariable("WHISPER_EXE_PATH");
        if (!string.IsNullOrWhiteSpace(envExe))
        {
            WhisperExePath = envExe;
        }

        var envModel = Environment.GetEnvironmentVariable("WHISPER_MODEL_PATH");
        if (!string.IsNullOrWhiteSpace(envModel))
        {
            WhisperModelPath = envModel;
        }

        var envLang = Environment.GetEnvironmentVariable("WHISPER_LANGUAGE");
        if (!string.IsNullOrWhiteSpace(envLang))
        {
            WhisperLanguage = envLang;
        }

        var envThreads = Environment.GetEnvironmentVariable("WHISPER_THREADS");
        if (!string.IsNullOrWhiteSpace(envThreads) && int.TryParse(envThreads, out var threads))
        {
            WhisperThreadsText = threads.ToString();
        }
    }

    private void SaveWhisperConfig()
    {
        try
        {
            var config = new WhisperGuiConfigFile
            {
                ExecutablePath = WhisperExePath,
                ModelPath = WhisperModelPath,
                Language = WhisperLanguage,
                Threads = int.TryParse(WhisperThreadsText, out var t) && t > 0 ? t : null,
                ExtraArgs = WhisperExtraArgs
            };
            var json = JsonSerializer.Serialize(config, WhisperConfigJsonOptions);
            var configPath = Path.Combine(Environment.CurrentDirectory, "whisper-config.json");
            File.WriteAllText(configPath, json);
            AppFileLogger.Write("WhisperConfig", $"已保存 Whisper 配置到 {configPath}");
        }
        catch (Exception ex)
        {
            AppFileLogger.Write("WhisperConfig", $"保存 whisper-config.json 失败：{ex.Message}");
        }
    }

    private sealed class WhisperGuiConfigFile
    {
        [JsonPropertyName("executablePath")]
        public string ExecutablePath { get; init; } = string.Empty;
        [JsonPropertyName("modelPath")]
        public string ModelPath { get; init; } = string.Empty;
        [JsonPropertyName("language")]
        public string Language { get; init; } = string.Empty;
        [JsonPropertyName("threads")]
        public int? Threads { get; init; }
        [JsonPropertyName("extraArgs")]
        public string ExtraArgs { get; init; } = string.Empty;
    }
}
