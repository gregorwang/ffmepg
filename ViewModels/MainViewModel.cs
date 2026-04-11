using System.Collections.ObjectModel;
using System.Collections.Specialized;
using System.ComponentModel;
using System.Globalization;
using System.Windows.Input;
using System.Windows.Data;
using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;
using AnimeTranscoder.Services;
using AnimeTranscoder.Workflows;

namespace AnimeTranscoder.ViewModels;

public sealed partial class MainViewModel : ObservableObject, IDisposable
{
    private readonly JsonSettingsService _settingsService;
    private readonly TaskHistoryService _taskHistoryService;
    private readonly UserDialogService _userDialogService;
    private readonly FfprobeService _ffprobeService;
    private readonly SubtitleSelectionService _subtitleSelectionService;
    private readonly HardwareDetectionService _hardwareDetectionService;
    private readonly OutputValidationService _outputValidationService;
    private readonly StoragePreflightService _storagePreflightService;
    private readonly NativeMediaCoreService _nativeMediaCoreService;
    private readonly DirectoryWatchService _directoryWatchService;
    private readonly FfmpegRunner _ffmpegRunner;
    private readonly FrameInspectionService _frameInspectionService;
    private readonly AudioExtractionService _audioExtractionService;
    private readonly VideoClipService _videoClipService;
    private readonly DouyinExportService _douyinExportService;
    private readonly DanmakuPreparationService _danmakuPreparationService;
    private readonly DanmakuBurnCommandBuilder _danmakuBurnCommandBuilder;
    private readonly DanmakuAssGeneratorService _danmakuAssGeneratorService;
    private readonly DanmakuExclusionRuleService _danmakuExclusionRuleService;
    private readonly OverlayFramePreviewService _overlayFramePreviewService;
    private readonly string[] _supportedInputExtensions = [".mkv", ".mp4", ".mov", ".m4v", ".avi", ".ts", ".m2ts", ".webm"];
    private CancellationTokenSource? _runCancellationTokenSource;
    private CancellationTokenSource? _audioExtractionCancellationTokenSource;
    private CancellationTokenSource? _clipCancellationTokenSource;
    private CancellationTokenSource? _douyinExportCancellationTokenSource;
    private AppSettings _settings;
    private string _statusMessage = "准备就绪";
    private string _logText = string.Empty;
    private string _hardwareSummary = "正在检测 ffmpeg 与 NVENC...";
    private string _nativeCoreSummary = "正在检测原生字幕分析模块...";
    private string _watchSummary = "目录监听未启动";
    private bool _isRunning;
    private bool _isDropTargetActive;
    private TranscodeJob? _selectedJob;
    private bool _isNvencAvailable;
    private string _historyStatusFilter = "全部";
    private DateTime? _historyDateFilter;
    private string _inspectionSummary = "尚未生成巡检截图";
    private string _inspectionOutputDirectory = string.Empty;
    private string _inspectionSource = string.Empty;
    private InspectionReportResult? _inspectionReport;
    private string _selectedPreviewTimeText = "5.0";
    private string _selectedPreviewImagePath = string.Empty;
    private string _selectedPreviewSummary = "尚未生成叠加预览";
    private string _selectedDanmakuAnalysisSummary = "尚未分析当前任务的弹幕";
    private string _danmakuSearchText = string.Empty;
    private string _danmakuKeywordBatchText = string.Empty;
    private string _selectedDanmakuModeFilter = "all";
    private bool _suppressDanmakuToggleSync;
    private string _audioInputPath = string.Empty;
    private string _audioMixBackgroundPath = string.Empty;
    private string _audioProbeSummary = "请选择媒体文件以分析音轨";
    private string _audioStatusMessage = "尚未开始";
    private string _audioStartTimeText = string.Empty;
    private string _audioDurationText = string.Empty;
    private string _audioOutputPathPreview = "未生成";
    private string _audioMixOutputPathPreview = "未生成";
    private string _audioMixSourceVolumeText = "1.0";
    private string _audioMixBackgroundVolumeText = "0.28";
    private string _audioSilenceSummary = "尚未执行静音检测";
    private string _audioSilenceThresholdText = "-30";
    private string _audioSilenceMinimumDurationText = "2";
    private double _audioProgress;
    private string _audioSpeed = string.Empty;
    private bool _audioNormalize = true;
    private bool _isAudioExtracting;
    private bool _isAudioSilenceDetecting;
    private AudioFormat _selectedAudioFormat = AudioFormat.AAC;
    private AudioTrackInfo? _selectedAudioTrack;
    private TimeSpan _audioSourceDuration;
    private string _clipInputPath = string.Empty;
    private string _pipOverlayPath = string.Empty;
    private string _clipProbeSummary = "请选择媒体文件以分析时长";
    private string _clipStatusMessage = "尚未开始";
    private string _clipStartTimeText = "00:00:00";
    private string _clipDurationText = "00:00:15";
    private string _concatSegmentsText = "00:00:00,00:00:15";
    private string _sceneDetectionThresholdText = "0.20";
    private string _autoSegmentMinimumDurationText = "1.50";
    private string _autoSegmentMaximumDurationText = "8.00";
    private string _clipOutputPathPreview = "未生成";
    private string _concatOutputPathPreview = "未生成";
    private string _verticalOutputPathPreview = "未生成";
    private string _gifOutputPathPreview = "未生成";
    private string _pipOutputPathPreview = "未生成";
    private string _clipSpeedFactorText = "1.25";
    private string _speedOutputPathPreview = "未生成";
    private string _reverseOutputPathPreview = "未生成";
    private string _pipScaleText = "0.28";
    private string _concatSummary = "每行一个片段，格式：开始时间,时长";
    private string _sceneDetectionSummary = "尚未执行场景检测";
    private string _autoSegmentSummary = "尚未生成自动分段";
    private string _blackDetectSummary = "尚未执行黑场检测";
    private string _freezeDetectSummary = "尚未执行冻帧检测";
    private string _coverCandidatesSummary = "尚未生成封面候选";
    private string _coverCandidatesDirectory = string.Empty;
    private string _blackDetectPictureThresholdText = "0.98";
    private string _blackDetectPixelThresholdText = "0.10";
    private string _blackDetectMinimumDurationText = "0.20";
    private string _freezeDetectNoiseThresholdText = "0.003";
    private string _freezeDetectMinimumDurationText = "0.50";
    private double _clipProgress;
    private string _clipSpeed = string.Empty;
    private bool _isClipRunning;
    private bool _clipHasAudio;
    private bool _hasValidConcatSegments;
    private TimeSpan _clipSourceDuration;
    private ClipMode _selectedClipMode = ClipMode.Fast;
    private VerticalMode _selectedVerticalMode = VerticalMode.BlurBackground;
    private PipCorner _selectedPipCorner = PipCorner.BottomRight;
    private string _douyinTitleText = "番剧高光片段";
    private string _douyinWatermarkText = "@我的抖音号";
    private string _douyinBgmPath = string.Empty;
    private string _douyinOutputPathPreview = "未生成";
    private string _douyinStatusMessage = "尚未开始";
    private string _douyinSourceVolumeText = "1.0";
    private string _douyinBgmVolumeText = "0.28";
    private string _douyinSubtitleSummary = "尚未分析字幕";
    private double _douyinProgress;
    private string _douyinSpeed = string.Empty;
    private bool _isDouyinExporting;
    private bool _douyinBurnSubtitles = true;
    private DouyinTemplatePreset _selectedDouyinTemplatePreset = DouyinTemplatePreset.BlurTitleWatermark;
    private int? _douyinSubtitleStreamOrdinal;

    public MainViewModel(
        JsonSettingsService settingsService,
        TaskHistoryService taskHistoryService,
        UserDialogService userDialogService,
        FfprobeService ffprobeService,
        SubtitleSelectionService subtitleSelectionService,
        HardwareDetectionService hardwareDetectionService,
        OutputValidationService outputValidationService,
        StoragePreflightService storagePreflightService,
        NativeMediaCoreService nativeMediaCoreService,
        DirectoryWatchService directoryWatchService,
        FfmpegRunner ffmpegRunner,
        FrameInspectionService frameInspectionService,
        AudioExtractionService audioExtractionService,
        AudioProcessingWorkflow audioProcessingWorkflow,
        TranscodeQueueWorkflow transcodeQueueWorkflow,
        VideoClipService videoClipService,
        DouyinExportService douyinExportService,
        DanmakuPreparationService danmakuPreparationService,
        DanmakuBurnCommandBuilder danmakuBurnCommandBuilder,
        DanmakuAssGeneratorService danmakuAssGeneratorService,
        DanmakuExclusionRuleService danmakuExclusionRuleService,
        OverlayFramePreviewService overlayFramePreviewService,
        ProjectFileService projectFileService,
        TranscriptDocumentService transcriptDocumentService,
        SelectionDocumentService selectionDocumentService,
        ProjectAudioWorkflow projectAudioWorkflow)
    {
        _settingsService = settingsService;
        _taskHistoryService = taskHistoryService;
        _userDialogService = userDialogService;
        _ffprobeService = ffprobeService;
        _subtitleSelectionService = subtitleSelectionService;
        _hardwareDetectionService = hardwareDetectionService;
        _outputValidationService = outputValidationService;
        _storagePreflightService = storagePreflightService;
        _nativeMediaCoreService = nativeMediaCoreService;
        _directoryWatchService = directoryWatchService;
        _ffmpegRunner = ffmpegRunner;
        _frameInspectionService = frameInspectionService;
        _audioExtractionService = audioExtractionService;
        _audioProcessingWorkflow = audioProcessingWorkflow;
        _transcodeQueueWorkflow = transcodeQueueWorkflow;
        _videoClipService = videoClipService;
        _douyinExportService = douyinExportService;
        _danmakuPreparationService = danmakuPreparationService;
        _danmakuBurnCommandBuilder = danmakuBurnCommandBuilder;
        _danmakuAssGeneratorService = danmakuAssGeneratorService;
        _danmakuExclusionRuleService = danmakuExclusionRuleService;
        _overlayFramePreviewService = overlayFramePreviewService;
        _projectFileService = projectFileService;
        _transcriptDocumentService = transcriptDocumentService;
        _selectionDocumentService = selectionDocumentService;
        _projectAudioWorkflow = projectAudioWorkflow;
        _settings = AppSettings.CreateDefault(ToolPathResolver.ResolveWorkspaceRoot());
        EditableSelectedDanmakuCommentsView = CollectionViewSource.GetDefaultView(EditableSelectedDanmakuComments);
        EditableSelectedDanmakuCommentsView.Filter = FilterEditableDanmakuComment;

        Jobs.CollectionChanged += OnJobsCollectionChanged;
        InspectionSamples.CollectionChanged += OnInspectionSamplesCollectionChanged;

        AddFilesCommand = new RelayCommand(_ => AddFiles());
        AddFolderCommand = new RelayCommand(_ => AddFolder());
        ScanInputDirectoryCommand = new RelayCommand(_ => ScanInputDirectory());
        ChooseInputDirectoryCommand = new RelayCommand(_ => ChooseInputDirectory());
        ChooseOutputDirectoryCommand = new RelayCommand(_ => ChooseOutputDirectory());
        ChooseAudioInputCommand = new AsyncRelayCommand(ChooseAudioInputAsync, () => !IsRunning && !IsAudioExtracting && !IsAudioSilenceDetecting && !IsClipRunning && !IsDouyinExporting);
        UseSelectedJobAsAudioInputCommand = new AsyncRelayCommand(UseSelectedJobAsAudioInputAsync, () => !IsRunning && !IsAudioExtracting && !IsAudioSilenceDetecting && !IsClipRunning && !IsDouyinExporting && SelectedJob is not null && File.Exists(SelectedJob.InputPath));
        ChooseClipInputCommand = new AsyncRelayCommand(ChooseClipInputAsync, () => !IsRunning && !IsAudioExtracting && !IsAudioSilenceDetecting && !IsClipRunning && !IsDouyinExporting);
        UseSelectedJobAsClipInputCommand = new AsyncRelayCommand(UseSelectedJobAsClipInputAsync, () => !IsRunning && !IsAudioExtracting && !IsAudioSilenceDetecting && !IsClipRunning && !IsDouyinExporting && SelectedJob is not null && File.Exists(SelectedJob.InputPath));
        ChooseSelectedJobDanmakuCommand = new RelayCommand(_ => ChooseSelectedJobDanmaku(), _ => SelectedJob is not null && !IsRunning);
        ClearSelectedJobDanmakuCommand = new RelayCommand(_ => ClearSelectedJobDanmaku(), _ => SelectedJob is not null && !string.IsNullOrWhiteSpace(SelectedJob.DanmakuInputPath) && !IsRunning);
        OpenSelectedDanmakuCommand = new RelayCommand(_ => OpenSelectedDanmaku(), _ => SelectedJob is not null && File.Exists(SelectedJob.DanmakuInputPath));
        OpenGeneratedDanmakuAssCommand = new RelayCommand(_ => OpenGeneratedDanmakuAss(), _ => SelectedJob is not null && File.Exists(SelectedJob.DanmakuAssPath));
        AnalyzeSelectedDanmakuCommand = new AsyncRelayCommand(AnalyzeSelectedDanmakuAsync, () => SelectedJob is not null && File.Exists(SelectedJob.InputPath) && !IsRunning);
        ClearSelectedDanmakuExclusionsCommand = new RelayCommand(_ => ClearSelectedDanmakuExclusions(), _ => SelectedJob is not null && !string.IsNullOrWhiteSpace(SelectedJob.DanmakuExcludedCommentKeys) && !IsRunning);
        ImportSelectedDanmakuRulesCommand = new AsyncRelayCommand(ImportSelectedDanmakuRulesAsync, () => SelectedJob is not null && !IsRunning);
        ExportSelectedDanmakuRulesCommand = new AsyncRelayCommand(ExportSelectedDanmakuRulesAsync, () => SelectedJob is not null && !IsRunning);
        DisableFilteredDanmakuCommand = new RelayCommand(_ => SetFilteredDanmakuEnabled(false), _ => HasEditableSelectedDanmakuComments && !IsRunning);
        EnableFilteredDanmakuCommand = new RelayCommand(_ => SetFilteredDanmakuEnabled(true), _ => HasEditableSelectedDanmakuComments && !IsRunning);
        DisableDanmakuByKeywordsCommand = new RelayCommand(_ => SetKeywordMatchedDanmakuEnabled(false), _ => HasEditableSelectedDanmakuComments && !IsRunning);
        EnableDanmakuByKeywordsCommand = new RelayCommand(_ => SetKeywordMatchedDanmakuEnabled(true), _ => HasEditableSelectedDanmakuComments && !IsRunning);
        RefreshSelectedPreviewCommand = new AsyncRelayCommand(RefreshSelectedPreviewAsync, () => SelectedJob is not null && File.Exists(SelectedJob.InputPath) && !IsRunning);
        RemoveSelectedCommand = new RelayCommand(_ => RemoveSelectedJob(), _ => SelectedJob is not null && !IsRunning);
        RetryFailedJobsCommand = new RelayCommand(_ => RetryFailedJobs(), _ => !IsRunning && Jobs.Any(job => job.Status is JobStatus.Failed or JobStatus.Cancelled));
        ClearFinishedJobsCommand = new RelayCommand(_ => ClearFinishedJobs(), _ => !IsRunning && Jobs.Any(job => job.Status is JobStatus.Success or JobStatus.Skipped or JobStatus.Cancelled));
        OpenOutputDirectoryCommand = new RelayCommand(_ => _userDialogService.OpenFolder(Settings.OutputDirectory));
        OpenAudioOutputDirectoryCommand = new RelayCommand(_ => OpenAudioOutputDirectory(), _ => !string.IsNullOrWhiteSpace(AudioInputPath));
        OpenAudioMixOutputDirectoryCommand = new RelayCommand(_ => OpenAudioMixOutputDirectory(), _ => !string.IsNullOrWhiteSpace(AudioInputPath));
        OpenClipOutputDirectoryCommand = new RelayCommand(_ => OpenClipOutputDirectory(), _ => !string.IsNullOrWhiteSpace(ClipInputPath));
        OpenConcatOutputDirectoryCommand = new RelayCommand(_ => OpenConcatOutputDirectory(), _ => !string.IsNullOrWhiteSpace(ClipInputPath));
        OpenVerticalOutputDirectoryCommand = new RelayCommand(_ => OpenVerticalOutputDirectory(), _ => !string.IsNullOrWhiteSpace(ClipInputPath));
        OpenGifOutputDirectoryCommand = new RelayCommand(_ => OpenGifOutputDirectory(), _ => !string.IsNullOrWhiteSpace(ClipInputPath));
        OpenPipOutputDirectoryCommand = new RelayCommand(_ => OpenPipOutputDirectory(), _ => !string.IsNullOrWhiteSpace(ClipInputPath));
        OpenVideoFxOutputDirectoryCommand = new RelayCommand(_ => OpenVideoFxOutputDirectory(), _ => !string.IsNullOrWhiteSpace(ClipInputPath));
        OpenDouyinOutputDirectoryCommand = new RelayCommand(_ => OpenDouyinOutputDirectory(), _ => !string.IsNullOrWhiteSpace(ClipInputPath));
        OpenLogDirectoryCommand = new RelayCommand(_ => _userDialogService.OpenFolder(AppFileLogger.LogDirectory));
        OpenSelectedOutputDirectoryCommand = new RelayCommand(_ => OpenSelectedOutputDirectory(), _ => SelectedJob is not null && !string.IsNullOrWhiteSpace(SelectedJob.OutputPath));
        OpenInspectionDirectoryCommand = new RelayCommand(_ => OpenInspectionDirectory(), _ => Directory.Exists(_inspectionOutputDirectory));
        OpenCoverCandidatesDirectoryCommand = new RelayCommand(_ => OpenCoverCandidatesDirectory(), _ => Directory.Exists(_coverCandidatesDirectory));
        OpenInspectionSampleCommand = new RelayCommand(path => OpenInspectionSample(path as string), path => path is string samplePath && File.Exists(samplePath));
        CaptureSelectedFrameCommand = new AsyncRelayCommand(CaptureSelectedFrameAsync, () => SelectedJob is not null && File.Exists(SelectedJob.InputPath));
        CaptureSelectedFrameSetCommand = new AsyncRelayCommand(CaptureSelectedFrameSetAsync, () => SelectedJob is not null && File.Exists(SelectedJob.InputPath));
        ExportInspectionReportJsonCommand = new AsyncRelayCommand(() => ExportInspectionReportAsync("json"), () => _inspectionReport is not null && HasInspectionSamples);
        ExportInspectionReportTextCommand = new AsyncRelayCommand(() => ExportInspectionReportAsync("txt"), () => _inspectionReport is not null && HasInspectionSamples);
        SaveSettingsCommand = new AsyncRelayCommand(SaveSettingsAsync);
        ChooseAudioMixBackgroundCommand = new RelayCommand(_ => ChooseAudioMixBackground(), _ => !IsRunning && !IsAudioExtracting && !IsAudioSilenceDetecting && !IsClipRunning && !IsDouyinExporting);
        ClearAudioMixBackgroundCommand = new RelayCommand(_ => ClearAudioMixBackground(), _ => !IsRunning && !IsAudioExtracting && !IsAudioSilenceDetecting && !IsClipRunning && !IsDouyinExporting && !string.IsNullOrWhiteSpace(AudioMixBackgroundPath));
        ExtractAudioCommand = new AsyncRelayCommand(ExtractAudioAsync, CanExtractAudio);
        StartAudioMixCommand = new AsyncRelayCommand(StartAudioMixAsync, CanStartAudioMix);
        DetectSilenceCommand = new AsyncRelayCommand(DetectSilenceAsync, CanDetectSilence);
        StartFastClipCommand = new AsyncRelayCommand(StartFastClipAsync, CanStartFastClip);
        StartGifPreviewCommand = new AsyncRelayCommand(StartGifPreviewAsync, CanStartFastClip);
        ChoosePipOverlayCommand = new RelayCommand(_ => ChoosePipOverlay(), _ => !IsRunning && !IsAudioExtracting && !IsAudioSilenceDetecting && !IsClipRunning && !IsDouyinExporting);
        ClearPipOverlayCommand = new RelayCommand(_ => ClearPipOverlay(), _ => !IsRunning && !IsAudioExtracting && !IsAudioSilenceDetecting && !IsClipRunning && !IsDouyinExporting && !string.IsNullOrWhiteSpace(PipOverlayPath));
        StartPictureInPictureCommand = new AsyncRelayCommand(StartPictureInPictureAsync, CanStartPictureInPicture);
        StartSpeedChangeCommand = new AsyncRelayCommand(StartSpeedChangeAsync, CanStartSpeedChange);
        StartReverseCommand = new AsyncRelayCommand(StartReverseAsync, CanStartFastClip);
        StartConcatCommand = new AsyncRelayCommand(StartConcatAsync, CanStartConcat);
        DetectScenesCommand = new AsyncRelayCommand(DetectScenesAsync, CanDetectScenes);
        GenerateAutoSegmentsCommand = new RelayCommand(_ => GenerateAutoSegmentsFromScenes(), _ => CanGenerateAutoSegments());
        DetectBlackSegmentsCommand = new AsyncRelayCommand(DetectBlackSegmentsAsync, CanDetectScenes);
        DetectFreezeSegmentsCommand = new AsyncRelayCommand(DetectFreezeSegmentsAsync, CanDetectScenes);
        GenerateCoverCandidatesCommand = new AsyncRelayCommand(GenerateCoverCandidatesAsync, CanGenerateCoverCandidates);
        StartVerticalAdaptCommand = new AsyncRelayCommand(StartVerticalAdaptAsync, CanStartVerticalAdapt);
        ChooseDouyinBgmCommand = new RelayCommand(_ => ChooseDouyinBgm(), _ => !IsRunning && !IsAudioExtracting && !IsAudioSilenceDetecting && !IsClipRunning && !IsDouyinExporting);
        ClearDouyinBgmCommand = new RelayCommand(_ => ClearDouyinBgm(), _ => !IsDouyinExporting && !string.IsNullOrWhiteSpace(DouyinBgmPath));
        StartDouyinExportCommand = new AsyncRelayCommand(StartDouyinExportAsync, CanStartDouyinExport);
        StartBatchDouyinExportCommand = new AsyncRelayCommand(StartBatchDouyinExportAsync, CanStartBatchDouyinExport);
        StartQueueCommand = new AsyncRelayCommand(StartQueueAsync, () => !IsRunning && !IsAudioExtracting && !IsAudioSilenceDetecting && !IsClipRunning && !IsDouyinExporting && Jobs.Count > 0);
        CancelCommand = new RelayCommand(_ => Cancel(), _ => IsRunning);
        CancelAudioExtractionCommand = new RelayCommand(_ => CancelAudioExtraction(), _ => IsAudioExtracting);
        CancelClipCommand = new RelayCommand(_ => CancelClip(), _ => IsClipRunning);
        CancelDouyinExportCommand = new RelayCommand(_ => CancelDouyinExport(), _ => IsDouyinExporting);
        ExportHistoryJsonCommand = new AsyncRelayCommand(() => ExportHistoryAsync("json"), () => FilteredHistoryEntries.Count > 0);
        ExportHistoryTextCommand = new AsyncRelayCommand(() => ExportHistoryAsync("txt"), () => FilteredHistoryEntries.Count > 0);
        ClearHistoryFiltersCommand = new RelayCommand(_ => ClearHistoryFilters(), _ => HistoryEntries.Count > 0);
        InitializeAudioProjectFeature();

        _ = InitializeAsync();
    }

    public ObservableCollection<TranscodeJob> Jobs { get; } = [];

    public ObservableCollection<TaskHistoryEntry> HistoryEntries { get; } = [];

    public ObservableCollection<DiagnosticFrameSample> InspectionSamples { get; } = [];

    public ObservableCollection<AudioTrackInfo> AudioTracks { get; } = [];

    public ObservableCollection<SilenceSegment> SilenceSegments { get; } = [];

    public ObservableCollection<ClipConcatSegment> ConcatSegments { get; } = [];

    public ObservableCollection<SceneCutPoint> SceneCutPoints { get; } = [];

    public ObservableCollection<DiagnosticFrameSample> CoverCandidates { get; } = [];

    public ObservableCollection<VideoAnalysisSegment> BlackSegments { get; } = [];

    public ObservableCollection<VideoAnalysisSegment> FreezeSegments { get; } = [];

    public ObservableCollection<DanmakuComment> SelectedDanmakuComments { get; } = [];
    public ObservableCollection<EditableDanmakuComment> EditableSelectedDanmakuComments { get; } = [];
    public ICollectionView EditableSelectedDanmakuCommentsView { get; }

    public AppSettings Settings
    {
        get => _settings;
        private set => SetProperty(ref _settings, value);
    }

    public string StatusMessage
    {
        get => _statusMessage;
        set => SetProperty(ref _statusMessage, value);
    }

    public string LogText
    {
        get => _logText;
        set => SetProperty(ref _logText, value);
    }

    public string HardwareSummary
    {
        get => _hardwareSummary;
        set => SetProperty(ref _hardwareSummary, value);
    }

    public string NativeCoreSummary
    {
        get => _nativeCoreSummary;
        set => SetProperty(ref _nativeCoreSummary, value);
    }

    public string WatchSummary
    {
        get => _watchSummary;
        set => SetProperty(ref _watchSummary, value);
    }

    public int TotalJobs => Jobs.Count;

    public int PendingJobs => Jobs.Count(job => job.Status is JobStatus.Pending or JobStatus.Probing or JobStatus.Ready);

    public int RunningJobs => Jobs.Count(job => job.Status == JobStatus.Running);

    public int SuccessJobs => Jobs.Count(job => job.Status == JobStatus.Success);

    public int FailedJobs => Jobs.Count(job => job.Status == JobStatus.Failed);

    public string QueueSummary => TotalJobs == 0
        ? "还没有待处理文件"
        : $"共 {TotalJobs} 个任务，已完成 {SuccessJobs} 个，失败 {FailedJobs} 个";

    public string SelectedJobTitle => SelectedJob?.FileName ?? "未选择任务";

    public string SelectedJobStatusText => SelectedJob?.StatusText ?? "请选择任务队列中的一项";

    public string SelectedJobMessage => SelectedJob?.Message ?? "这里会显示当前任务的状态说明、失败原因或跳过原因。";

    public string SelectedJobInputPath => SelectedJob?.InputPath ?? "未选择";

    public string SelectedJobOutputPath => SelectedJob?.OutputPath ?? "未选择";

    public string SelectedJobEncoder => string.IsNullOrWhiteSpace(SelectedJob?.EncoderUsed) ? "未开始" : SelectedJob!.EncoderUsed;

    public string SelectedJobSubtitleAnalysis => string.IsNullOrWhiteSpace(SelectedJob?.SubtitleAnalysisSource) ? "未分析" : SelectedJob!.SubtitleAnalysisSource;

    public string SelectedJobSubtitleKind => string.IsNullOrWhiteSpace(SelectedJob?.SubtitleKindSummary) ? "未分析" : SelectedJob!.SubtitleKindSummary;

    public string SelectedJobProgressText => SelectedJob is null ? "0%" : $"{SelectedJob.Progress:F0}%";

    public string SelectedJobDanmakuSource => string.IsNullOrWhiteSpace(SelectedJob?.DanmakuSourceSummary) ? "未配置" : SelectedJob!.DanmakuSourceSummary;

    public string SelectedJobDanmakuInputPath => string.IsNullOrWhiteSpace(SelectedJob?.DanmakuInputPath) ? "未绑定" : SelectedJob!.DanmakuInputPath;

    public string SelectedPreviewTimeText
    {
        get => _selectedPreviewTimeText;
        set => SetProperty(ref _selectedPreviewTimeText, value);
    }

    public string SelectedPreviewImagePath
    {
        get => _selectedPreviewImagePath;
        private set => SetProperty(ref _selectedPreviewImagePath, value);
    }

    public string SelectedPreviewSummary
    {
        get => _selectedPreviewSummary;
        private set => SetProperty(ref _selectedPreviewSummary, value);
    }

    public string SelectedDanmakuAnalysisSummary
    {
        get => _selectedDanmakuAnalysisSummary;
        private set => SetProperty(ref _selectedDanmakuAnalysisSummary, value);
    }

    public string DanmakuSearchText
    {
        get => _danmakuSearchText;
        set
        {
            if (SetProperty(ref _danmakuSearchText, value))
            {
                EditableSelectedDanmakuCommentsView.Refresh();
                RaisePropertyChanged(nameof(FilteredDanmakuCountSummary));
            }
        }
    }

    public string DanmakuKeywordBatchText
    {
        get => _danmakuKeywordBatchText;
        set => SetProperty(ref _danmakuKeywordBatchText, value);
    }

    public string SelectedDanmakuModeFilter
    {
        get => _selectedDanmakuModeFilter;
        set
        {
            if (SetProperty(ref _selectedDanmakuModeFilter, value))
            {
                EditableSelectedDanmakuCommentsView.Refresh();
                RaisePropertyChanged(nameof(FilteredDanmakuCountSummary));
            }
        }
    }

    public string SelectedJobDanmakuPreparation => string.IsNullOrWhiteSpace(SelectedJob?.DanmakuPreparationSummary) ? "未分析" : SelectedJob!.DanmakuPreparationSummary;

    public string SelectedJobDanmakuXmlStats => SelectedJob is null || SelectedJob.DanmakuXmlCommentCount <= 0
        ? "未分析"
        : $"{SelectedJob.DanmakuXmlCommentCount} -> {SelectedJob.DanmakuKeptCommentCount}";

    public string SelectedJobDanmakuAssPath => string.IsNullOrWhiteSpace(SelectedJob?.DanmakuAssPath) ? "未生成" : SelectedJob!.DanmakuAssPath;

    public bool HasSelectedDanmakuComments => SelectedDanmakuComments.Count > 0;

    public bool HasEditableSelectedDanmakuComments => EditableSelectedDanmakuComments.Count > 0;

    public int SelectedDanmakuDisabledCount => EditableSelectedDanmakuComments.Count(comment => !comment.IsEnabled);

    public string FilteredDanmakuCountSummary => $"{EditableSelectedDanmakuCommentsView.Cast<object>().Count()} / {EditableSelectedDanmakuComments.Count} 条匹配当前筛选";

    public bool HasInspectionSamples => InspectionSamples.Count > 0;

    public string InspectionSummary => _inspectionSummary;

    public string InspectionOutputDirectory => string.IsNullOrWhiteSpace(_inspectionOutputDirectory)
        ? "未生成"
        : _inspectionOutputDirectory;

    public string InspectionSource => string.IsNullOrWhiteSpace(_inspectionSource)
        ? "未生成"
        : _inspectionSource;

    public string InspectionReportHeadline => _inspectionReport?.Summary ?? "尚未生成巡检报告";

    public string InspectionAttentionSummary => _inspectionReport is null
        ? "先生成巡检截图，再查看自动分析结果。"
        : $"需关注 {_inspectionReport.AttentionSamples} / {_inspectionReport.TotalSamples} 张";

    public bool IsDropTargetActive
    {
        get => _isDropTargetActive;
        set => SetProperty(ref _isDropTargetActive, value);
    }

    public bool IsRunning
    {
        get => _isRunning;
        set
        {
            if (SetProperty(ref _isRunning, value))
            {
                NotifyCommandStateChanged();
            }
        }
    }

    public TranscodeJob? SelectedJob
    {
        get => _selectedJob;
        set
        {
            if (SetProperty(ref _selectedJob, value))
            {
                SelectedPreviewImagePath = string.Empty;
                SelectedPreviewTimeText = value is null
                    ? "5.0"
                    : DetermineFrameSampleTimeSeconds(value).ToString("0.###", CultureInfo.InvariantCulture);
                SelectedPreviewSummary = value is null
                    ? "尚未生成叠加预览"
                    : "请点击刷新预览查看当前字幕/弹幕叠加效果";
                SelectedDanmakuAnalysisSummary = value is null
                    ? "尚未分析当前任务的弹幕"
                    : string.IsNullOrWhiteSpace(value.DanmakuPreparationSummary)
                        ? "请先点击重新分析弹幕"
                        : value.DanmakuPreparationSummary;
                DanmakuSearchText = string.Empty;
                DanmakuKeywordBatchText = string.Empty;
                SelectedDanmakuModeFilter = "all";
                LoadSelectedDanmakuCommentsFromJob(value);
                RaiseSelectedJobProperties();
                NotifyCommandStateChanged();
            }
        }
    }

    public string HistoryStatusFilter
    {
        get => _historyStatusFilter;
        set
        {
            if (SetProperty(ref _historyStatusFilter, value))
            {
                RaiseHistoryProperties();
            }
        }
    }

    public DateTime? HistoryDateFilter
    {
        get => _historyDateFilter;
        set
        {
            if (SetProperty(ref _historyDateFilter, value))
            {
                RaiseHistoryProperties();
            }
        }
    }

    public IReadOnlyList<TaskHistoryEntry> FilteredHistoryEntries => HistoryEntries
        .Where(MatchesHistoryFilter)
        .OrderByDescending(entry => entry.RecordedAt)
        .ToList();

    public int HistoryCount => HistoryEntries.Count;

    public string HistorySummary => HistoryEntries.Count == 0
        ? "暂无历史任务"
        : $"历史共 {HistoryEntries.Count} 条，当前筛选后 {FilteredHistoryEntries.Count} 条";

    public string AudioInputPath
    {
        get => _audioInputPath;
        private set
        {
            if (SetProperty(ref _audioInputPath, value))
            {
                RaisePropertyChanged(nameof(AudioInputFileName));
            }
        }
    }

    public string AudioInputFileName => string.IsNullOrWhiteSpace(AudioInputPath)
        ? "未选择媒体文件"
        : Path.GetFileName(AudioInputPath);

    public string AudioMixBackgroundPath
    {
        get => _audioMixBackgroundPath;
        private set
        {
            if (SetProperty(ref _audioMixBackgroundPath, value))
            {
                NotifyCommandStateChanged();
            }
        }
    }

    public string AudioProbeSummary
    {
        get => _audioProbeSummary;
        private set => SetProperty(ref _audioProbeSummary, value);
    }

    public string AudioStatusMessage
    {
        get => _audioStatusMessage;
        private set => SetProperty(ref _audioStatusMessage, value);
    }

    public string AudioStartTimeText
    {
        get => _audioStartTimeText;
        set => SetProperty(ref _audioStartTimeText, value);
    }

    public string AudioDurationText
    {
        get => _audioDurationText;
        set => SetProperty(ref _audioDurationText, value);
    }

    public string AudioOutputPathPreview
    {
        get => _audioOutputPathPreview;
        private set => SetProperty(ref _audioOutputPathPreview, value);
    }

    public string AudioMixOutputPathPreview
    {
        get => _audioMixOutputPathPreview;
        private set => SetProperty(ref _audioMixOutputPathPreview, value);
    }

    public string AudioMixSourceVolumeText
    {
        get => _audioMixSourceVolumeText;
        set => SetProperty(ref _audioMixSourceVolumeText, value);
    }

    public string AudioMixBackgroundVolumeText
    {
        get => _audioMixBackgroundVolumeText;
        set => SetProperty(ref _audioMixBackgroundVolumeText, value);
    }

    public string AudioSilenceSummary
    {
        get => _audioSilenceSummary;
        private set => SetProperty(ref _audioSilenceSummary, value);
    }

    public string AudioSilenceThresholdText
    {
        get => _audioSilenceThresholdText;
        set => SetProperty(ref _audioSilenceThresholdText, value);
    }

    public string AudioSilenceMinimumDurationText
    {
        get => _audioSilenceMinimumDurationText;
        set => SetProperty(ref _audioSilenceMinimumDurationText, value);
    }

    public string AudioOutputDirectoryPath => Path.Combine(Settings.OutputDirectory, "audio_exports");

    public string AudioMixOutputDirectoryPath => Path.Combine(Settings.OutputDirectory, "audio_mix");

    public string AudioSourceDurationText => _audioSourceDuration > TimeSpan.Zero
        ? _audioSourceDuration.ToString(@"hh\:mm\:ss\.fff")
        : "未知";

    public double AudioProgress
    {
        get => _audioProgress;
        private set
        {
            if (SetProperty(ref _audioProgress, value))
            {
                RaisePropertyChanged(nameof(AudioProgressText));
            }
        }
    }

    public string AudioProgressText => $"{AudioProgress:F0}%";

    public string AudioSpeed
    {
        get => _audioSpeed;
        private set
        {
            if (SetProperty(ref _audioSpeed, value))
            {
                RaisePropertyChanged(nameof(AudioSpeedText));
            }
        }
    }

    public string AudioSpeedText => string.IsNullOrWhiteSpace(AudioSpeed) ? "未开始" : AudioSpeed;

    public bool AudioNormalize
    {
        get => _audioNormalize;
        set
        {
            if (SetProperty(ref _audioNormalize, value))
            {
                RefreshAudioOutputPathPreview();
                NotifyCommandStateChanged();
            }
        }
    }

    public bool IsAudioExtracting
    {
        get => _isAudioExtracting;
        private set
        {
            if (SetProperty(ref _isAudioExtracting, value))
            {
                NotifyCommandStateChanged();
            }
        }
    }

    public bool IsAudioSilenceDetecting
    {
        get => _isAudioSilenceDetecting;
        private set
        {
            if (SetProperty(ref _isAudioSilenceDetecting, value))
            {
                NotifyCommandStateChanged();
            }
        }
    }

    public AudioFormat SelectedAudioFormat
    {
        get => _selectedAudioFormat;
        set
        {
            if (SetProperty(ref _selectedAudioFormat, value))
            {
                RefreshAudioOutputPathPreview();
                NotifyCommandStateChanged();
            }
        }
    }

    public AudioTrackInfo? SelectedAudioTrack
    {
        get => _selectedAudioTrack;
        set
        {
            if (SetProperty(ref _selectedAudioTrack, value))
            {
                NotifyCommandStateChanged();
            }
        }
    }

    public string ClipInputPath
    {
        get => _clipInputPath;
        private set
        {
            if (SetProperty(ref _clipInputPath, value))
            {
                RaisePropertyChanged(nameof(ClipInputFileName));
            }
        }
    }

    public string ClipInputFileName => string.IsNullOrWhiteSpace(ClipInputPath)
        ? "未选择媒体文件"
        : Path.GetFileName(ClipInputPath);

    public string PipOverlayPath
    {
        get => _pipOverlayPath;
        private set
        {
            if (SetProperty(ref _pipOverlayPath, value))
            {
                RefreshPipOutputPathPreview();
                NotifyCommandStateChanged();
            }
        }
    }

    public string ClipProbeSummary
    {
        get => _clipProbeSummary;
        private set => SetProperty(ref _clipProbeSummary, value);
    }

    public string ClipStatusMessage
    {
        get => _clipStatusMessage;
        private set => SetProperty(ref _clipStatusMessage, value);
    }

    public string ClipStartTimeText
    {
        get => _clipStartTimeText;
        set => SetProperty(ref _clipStartTimeText, value);
    }

    public string ClipDurationText
    {
        get => _clipDurationText;
        set => SetProperty(ref _clipDurationText, value);
    }

    public string ConcatSegmentsText
    {
        get => _concatSegmentsText;
        set
        {
            if (SetProperty(ref _concatSegmentsText, value))
            {
                RefreshConcatSegmentsPreview();
                NotifyCommandStateChanged();
            }
        }
    }

    public string SceneDetectionThresholdText
    {
        get => _sceneDetectionThresholdText;
        set => SetProperty(ref _sceneDetectionThresholdText, value);
    }

    public string AutoSegmentMinimumDurationText
    {
        get => _autoSegmentMinimumDurationText;
        set => SetProperty(ref _autoSegmentMinimumDurationText, value);
    }

    public string AutoSegmentMaximumDurationText
    {
        get => _autoSegmentMaximumDurationText;
        set => SetProperty(ref _autoSegmentMaximumDurationText, value);
    }

    public string BlackDetectPictureThresholdText
    {
        get => _blackDetectPictureThresholdText;
        set => SetProperty(ref _blackDetectPictureThresholdText, value);
    }

    public string BlackDetectPixelThresholdText
    {
        get => _blackDetectPixelThresholdText;
        set => SetProperty(ref _blackDetectPixelThresholdText, value);
    }

    public string BlackDetectMinimumDurationText
    {
        get => _blackDetectMinimumDurationText;
        set => SetProperty(ref _blackDetectMinimumDurationText, value);
    }

    public string FreezeDetectNoiseThresholdText
    {
        get => _freezeDetectNoiseThresholdText;
        set => SetProperty(ref _freezeDetectNoiseThresholdText, value);
    }

    public string FreezeDetectMinimumDurationText
    {
        get => _freezeDetectMinimumDurationText;
        set => SetProperty(ref _freezeDetectMinimumDurationText, value);
    }

    public string ClipOutputPathPreview
    {
        get => _clipOutputPathPreview;
        private set => SetProperty(ref _clipOutputPathPreview, value);
    }

    public string ConcatOutputPathPreview
    {
        get => _concatOutputPathPreview;
        private set => SetProperty(ref _concatOutputPathPreview, value);
    }

    public string VerticalOutputPathPreview
    {
        get => _verticalOutputPathPreview;
        private set => SetProperty(ref _verticalOutputPathPreview, value);
    }

    public string GifOutputPathPreview
    {
        get => _gifOutputPathPreview;
        private set => SetProperty(ref _gifOutputPathPreview, value);
    }

    public string PipOutputPathPreview
    {
        get => _pipOutputPathPreview;
        private set => SetProperty(ref _pipOutputPathPreview, value);
    }

    public string PipScaleText
    {
        get => _pipScaleText;
        set
        {
            if (SetProperty(ref _pipScaleText, value))
            {
                RefreshPipOutputPathPreview();
                NotifyCommandStateChanged();
            }
        }
    }

    public string ClipSpeedFactorText
    {
        get => _clipSpeedFactorText;
        set
        {
            if (SetProperty(ref _clipSpeedFactorText, value))
            {
                RefreshSpeedOutputPathPreview();
                NotifyCommandStateChanged();
            }
        }
    }

    public string SpeedOutputPathPreview
    {
        get => _speedOutputPathPreview;
        private set => SetProperty(ref _speedOutputPathPreview, value);
    }

    public string ReverseOutputPathPreview
    {
        get => _reverseOutputPathPreview;
        private set => SetProperty(ref _reverseOutputPathPreview, value);
    }

    public string DouyinTitleText
    {
        get => _douyinTitleText;
        set => SetProperty(ref _douyinTitleText, value);
    }

    public string DouyinWatermarkText
    {
        get => _douyinWatermarkText;
        set => SetProperty(ref _douyinWatermarkText, value);
    }

    public string DouyinBgmPath
    {
        get => _douyinBgmPath;
        private set
        {
            if (SetProperty(ref _douyinBgmPath, value))
            {
                NotifyCommandStateChanged();
            }
        }
    }

    public string DouyinOutputPathPreview
    {
        get => _douyinOutputPathPreview;
        private set => SetProperty(ref _douyinOutputPathPreview, value);
    }

    public string DouyinStatusMessage
    {
        get => _douyinStatusMessage;
        private set => SetProperty(ref _douyinStatusMessage, value);
    }

    public string DouyinSourceVolumeText
    {
        get => _douyinSourceVolumeText;
        set => SetProperty(ref _douyinSourceVolumeText, value);
    }

    public string DouyinBgmVolumeText
    {
        get => _douyinBgmVolumeText;
        set => SetProperty(ref _douyinBgmVolumeText, value);
    }

    public string DouyinSubtitleSummary
    {
        get => _douyinSubtitleSummary;
        private set => SetProperty(ref _douyinSubtitleSummary, value);
    }

    public bool DouyinBurnSubtitles
    {
        get => _douyinBurnSubtitles;
        set => SetProperty(ref _douyinBurnSubtitles, value);
    }

    public double DouyinProgress
    {
        get => _douyinProgress;
        private set
        {
            if (SetProperty(ref _douyinProgress, value))
            {
                RaisePropertyChanged(nameof(DouyinProgressText));
            }
        }
    }

    public string DouyinProgressText => $"{DouyinProgress:F0}%";

    public string DouyinSpeed
    {
        get => _douyinSpeed;
        private set
        {
            if (SetProperty(ref _douyinSpeed, value))
            {
                RaisePropertyChanged(nameof(DouyinSpeedText));
            }
        }
    }

    public string DouyinSpeedText => string.IsNullOrWhiteSpace(DouyinSpeed) ? "未开始" : DouyinSpeed;

    public bool IsDouyinExporting
    {
        get => _isDouyinExporting;
        private set
        {
            if (SetProperty(ref _isDouyinExporting, value))
            {
                NotifyCommandStateChanged();
            }
        }
    }

    public string ClipOutputDirectoryPath => Path.Combine(Settings.OutputDirectory, "video_clips");

    public string ConcatOutputDirectoryPath => Path.Combine(Settings.OutputDirectory, "video_concat");

    public string VerticalOutputDirectoryPath => Path.Combine(Settings.OutputDirectory, "video_vertical");

    public string GifOutputDirectoryPath => Path.Combine(Settings.OutputDirectory, "video_gifs");

    public string VideoFxOutputDirectoryPath => Path.Combine(Settings.OutputDirectory, "video_fx");

    public string PipOutputDirectoryPath => Path.Combine(Settings.OutputDirectory, "video_pip");

    public string DouyinOutputDirectoryPath => Path.Combine(Settings.OutputDirectory, "douyin_exports");

    public string ClipSourceDurationText => _clipSourceDuration > TimeSpan.Zero
        ? _clipSourceDuration.ToString(@"hh\:mm\:ss\.fff")
        : "未知";

    public double ClipProgress
    {
        get => _clipProgress;
        private set
        {
            if (SetProperty(ref _clipProgress, value))
            {
                RaisePropertyChanged(nameof(ClipProgressText));
            }
        }
    }

    public string ClipProgressText => $"{ClipProgress:F0}%";

    public string ClipSpeed
    {
        get => _clipSpeed;
        private set
        {
            if (SetProperty(ref _clipSpeed, value))
            {
                RaisePropertyChanged(nameof(ClipSpeedText));
            }
        }
    }

    public string ClipSpeedText => string.IsNullOrWhiteSpace(ClipSpeed) ? "未开始" : ClipSpeed;

    public bool IsClipRunning
    {
        get => _isClipRunning;
        private set
        {
            if (SetProperty(ref _isClipRunning, value))
            {
                NotifyCommandStateChanged();
            }
        }
    }

    public ClipMode SelectedClipMode
    {
        get => _selectedClipMode;
        set
        {
            if (SetProperty(ref _selectedClipMode, value))
            {
                RaisePropertyChanged(nameof(SelectedClipModeSummary));
            }
        }
    }

    public string SelectedClipModeSummary => SelectedClipMode == ClipMode.Fast
        ? "无损快切"
        : $"精准裁剪 ({_hardwareDetectionService.ResolveVideoEncoder(Settings.VideoEncoderMode, _isNvencAvailable)})";

    public PipCorner SelectedPipCorner
    {
        get => _selectedPipCorner;
        set
        {
            if (SetProperty(ref _selectedPipCorner, value))
            {
                RefreshPipOutputPathPreview();
            }
        }
    }

    public string ConcatSummary
    {
        get => _concatSummary;
        private set => SetProperty(ref _concatSummary, value);
    }

    public string AutoSegmentSummary
    {
        get => _autoSegmentSummary;
        private set => SetProperty(ref _autoSegmentSummary, value);
    }

    public string SceneDetectionSummary
    {
        get => _sceneDetectionSummary;
        private set => SetProperty(ref _sceneDetectionSummary, value);
    }

    public string BlackDetectSummary
    {
        get => _blackDetectSummary;
        private set => SetProperty(ref _blackDetectSummary, value);
    }

    public string FreezeDetectSummary
    {
        get => _freezeDetectSummary;
        private set => SetProperty(ref _freezeDetectSummary, value);
    }

    public string CoverCandidatesSummary
    {
        get => _coverCandidatesSummary;
        private set => SetProperty(ref _coverCandidatesSummary, value);
    }

    public string CoverCandidatesDirectory
    {
        get => string.IsNullOrWhiteSpace(_coverCandidatesDirectory) ? "未生成" : _coverCandidatesDirectory;
        private set => SetProperty(ref _coverCandidatesDirectory, value);
    }

    public VerticalMode SelectedVerticalMode
    {
        get => _selectedVerticalMode;
        set
        {
            if (SetProperty(ref _selectedVerticalMode, value))
            {
                RefreshVerticalOutputPathPreview();
                NotifyCommandStateChanged();
            }
        }
    }

    public DouyinTemplatePreset SelectedDouyinTemplatePreset
    {
        get => _selectedDouyinTemplatePreset;
        set
        {
            if (SetProperty(ref _selectedDouyinTemplatePreset, value))
            {
                RefreshDouyinOutputPathPreview();
                RaisePropertyChanged(nameof(SelectedDouyinTemplateSummary));
            }
        }
    }

    public string SelectedDouyinTemplateSummary => SelectedDouyinTemplatePreset switch
    {
        DouyinTemplatePreset.CropTitleWatermark => "中心裁切 9:16 + 标题 + 水印",
        DouyinTemplatePreset.BlurBgmBoost => "模糊背景 9:16 + 标题 + 水印 + BGM 混入",
        _ => "模糊背景 9:16 + 标题 + 水印"
    };

    public ICommand AddFilesCommand { get; }
    public ICommand AddFolderCommand { get; }
    public ICommand ScanInputDirectoryCommand { get; }
    public ICommand ChooseInputDirectoryCommand { get; }
    public ICommand ChooseOutputDirectoryCommand { get; }
    public ICommand ChooseAudioInputCommand { get; }
    public ICommand UseSelectedJobAsAudioInputCommand { get; }
    public ICommand ChooseClipInputCommand { get; }
    public ICommand UseSelectedJobAsClipInputCommand { get; }
    public ICommand ChooseSelectedJobDanmakuCommand { get; }
    public ICommand ClearSelectedJobDanmakuCommand { get; }
    public ICommand OpenSelectedDanmakuCommand { get; }
    public ICommand OpenGeneratedDanmakuAssCommand { get; }
    public ICommand AnalyzeSelectedDanmakuCommand { get; }
    public ICommand ClearSelectedDanmakuExclusionsCommand { get; }
    public ICommand ImportSelectedDanmakuRulesCommand { get; }
    public ICommand ExportSelectedDanmakuRulesCommand { get; }
    public ICommand DisableFilteredDanmakuCommand { get; }
    public ICommand EnableFilteredDanmakuCommand { get; }
    public ICommand DisableDanmakuByKeywordsCommand { get; }
    public ICommand EnableDanmakuByKeywordsCommand { get; }
    public ICommand RefreshSelectedPreviewCommand { get; }
    public ICommand RemoveSelectedCommand { get; }
    public ICommand RetryFailedJobsCommand { get; }
    public ICommand ClearFinishedJobsCommand { get; }
    public ICommand OpenOutputDirectoryCommand { get; }
    public ICommand OpenAudioOutputDirectoryCommand { get; }
    public ICommand OpenAudioMixOutputDirectoryCommand { get; }
    public ICommand OpenClipOutputDirectoryCommand { get; }
    public ICommand OpenConcatOutputDirectoryCommand { get; }
    public ICommand OpenVerticalOutputDirectoryCommand { get; }
    public ICommand OpenGifOutputDirectoryCommand { get; }
    public ICommand OpenPipOutputDirectoryCommand { get; }
    public ICommand OpenVideoFxOutputDirectoryCommand { get; }
    public ICommand OpenDouyinOutputDirectoryCommand { get; }
    public ICommand OpenLogDirectoryCommand { get; }
    public ICommand OpenSelectedOutputDirectoryCommand { get; }
    public ICommand OpenInspectionDirectoryCommand { get; }
    public ICommand OpenCoverCandidatesDirectoryCommand { get; }
    public ICommand OpenInspectionSampleCommand { get; }
    public ICommand CaptureSelectedFrameCommand { get; }
    public ICommand CaptureSelectedFrameSetCommand { get; }
    public ICommand ExportInspectionReportJsonCommand { get; }
    public ICommand ExportInspectionReportTextCommand { get; }
    public ICommand SaveSettingsCommand { get; }
    public ICommand ChooseAudioMixBackgroundCommand { get; }
    public ICommand ClearAudioMixBackgroundCommand { get; }
    public ICommand ExtractAudioCommand { get; }
    public ICommand StartAudioMixCommand { get; }
    public ICommand DetectSilenceCommand { get; }
    public ICommand StartFastClipCommand { get; }
    public ICommand StartGifPreviewCommand { get; }
    public ICommand ChoosePipOverlayCommand { get; }
    public ICommand ClearPipOverlayCommand { get; }
    public ICommand StartPictureInPictureCommand { get; }
    public ICommand StartSpeedChangeCommand { get; }
    public ICommand StartReverseCommand { get; }
    public ICommand StartConcatCommand { get; }
    public ICommand DetectScenesCommand { get; }
    public ICommand GenerateAutoSegmentsCommand { get; }
    public ICommand DetectBlackSegmentsCommand { get; }
    public ICommand DetectFreezeSegmentsCommand { get; }
    public ICommand GenerateCoverCandidatesCommand { get; }
    public ICommand StartVerticalAdaptCommand { get; }
    public ICommand ChooseDouyinBgmCommand { get; }
    public ICommand ClearDouyinBgmCommand { get; }
    public ICommand StartDouyinExportCommand { get; }
    public ICommand StartBatchDouyinExportCommand { get; }
    public ICommand StartQueueCommand { get; }
    public ICommand CancelCommand { get; }
    public ICommand CancelAudioExtractionCommand { get; }
    public ICommand CancelClipCommand { get; }
    public ICommand CancelDouyinExportCommand { get; }
    public ICommand ExportHistoryJsonCommand { get; }
    public ICommand ExportHistoryTextCommand { get; }
    public ICommand ClearHistoryFiltersCommand { get; }

    public event Action<string, string>? QueueCompleted;

    public void AddPaths(IEnumerable<string> incomingPaths)
    {
        AddPathsCore(incomingPaths);
    }

    private int AddPathsCore(IEnumerable<string> incomingPaths)
    {
        var files = ExpandIncomingPaths(incomingPaths)
            .Where(path => _supportedInputExtensions.Contains(Path.GetExtension(path), StringComparer.OrdinalIgnoreCase))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();

        var addedCount = 0;

        foreach (var file in files)
        {
            if (Jobs.Any(job => string.Equals(job.InputPath, file, StringComparison.OrdinalIgnoreCase)))
            {
                continue;
            }

            Jobs.Add(new TranscodeJob
            {
                InputPath = file,
                OutputPath = BuildOutputPath(file),
                Status = JobStatus.Pending,
                Message = "已加入队列"
            });
            addedCount++;
        }

        StatusMessage = $"已加入 {addedCount} 个文件";
        RaiseQueueSummaryProperties();
        NotifyCommandStateChanged();
        return addedCount;
    }

    private async Task InitializeAsync()
    {
        try
        {
            Settings = await _settingsService.LoadAsync();
            Settings.PropertyChanged += SettingsOnPropertyChanged;
            Directory.CreateDirectory(Settings.OutputDirectory);
            RaisePropertyChanged(nameof(AudioOutputDirectoryPath));
            RefreshAudioOutputPathPreview();
            RaisePropertyChanged(nameof(AudioMixOutputDirectoryPath));
            RefreshAudioMixOutputPathPreview();
            RaisePropertyChanged(nameof(ClipOutputDirectoryPath));
            RaisePropertyChanged(nameof(ConcatOutputDirectoryPath));
            RaisePropertyChanged(nameof(VerticalOutputDirectoryPath));
            RaisePropertyChanged(nameof(GifOutputDirectoryPath));
            RaisePropertyChanged(nameof(PipOutputDirectoryPath));
            RaisePropertyChanged(nameof(VideoFxOutputDirectoryPath));
            RaisePropertyChanged(nameof(DouyinOutputDirectoryPath));
            RefreshClipOutputPathPreview();
            RefreshConcatOutputPathPreview();
            RefreshVerticalOutputPathPreview();
            RefreshGifOutputPathPreview();
            RefreshPipOutputPathPreview();
            RefreshSpeedOutputPathPreview();
            RefreshReverseOutputPathPreview();
            RefreshDouyinOutputPathPreview();
            RefreshConcatSegmentsPreview();

            foreach (var entry in await _taskHistoryService.LoadAsync())
            {
                HistoryEntries.Add(entry);
            }

            var hardware = await _hardwareDetectionService.DetectAsync();
            _isNvencAvailable = hardware.IsNvencAvailable;
            HardwareSummary = hardware.IsNvencAvailable
                ? $"已检测到 NVIDIA NVENC | ffmpeg: {hardware.FfmpegPath}"
                : $"未检测到 NVENC，将自动回退到 CPU 编码 | ffmpeg: {hardware.FfmpegPath}";
            RaisePropertyChanged(nameof(SelectedClipModeSummary));

            NativeCoreSummary = _nativeMediaCoreService.StatusSummary;
            UpdateDirectoryWatcher();
            AppendLog($"已加载设置文件：{_settingsService.SettingsPath}");
            AppendLog($"已加载历史任务：{HistoryEntries.Count} 条");
            AppendLog($"运行日志：{AppFileLogger.CurrentLogPath}");
            RaiseHistoryProperties();
        }
        catch (Exception ex)
        {
            HardwareSummary = "硬件能力检测失败";
            NativeCoreSummary = "原生字幕分析模块初始化失败";
            AppendLog(ex.Message);
        }
    }

    private void AddFiles()
    {
        AddPaths(_userDialogService.PickFiles());
    }

    private void AddFolder()
    {
        var path = _userDialogService.PickFolder(Settings.InputDirectory);
        if (!string.IsNullOrWhiteSpace(path))
        {
            AddPaths([path]);
        }
    }

    private void ScanInputDirectory()
    {
        if (Directory.Exists(Settings.InputDirectory))
        {
            AddPaths([Settings.InputDirectory]);
        }
    }

    private void ChooseInputDirectory()
    {
        var path = _userDialogService.PickFolder(Settings.InputDirectory);
        if (!string.IsNullOrWhiteSpace(path))
        {
            Settings.InputDirectory = path;
            StatusMessage = $"输入目录已设为：{path}";
        }
    }

    private void ChooseOutputDirectory()
    {
        var path = _userDialogService.PickFolder(Settings.OutputDirectory);
        if (!string.IsNullOrWhiteSpace(path))
        {
            Settings.OutputDirectory = path;
            StatusMessage = $"输出目录已设为：{path}";
            RecalculateOutputPaths();
        }
    }

    private async Task ChooseAudioInputAsync()
    {
        var path = _userDialogService.PickMediaFile(Settings.InputDirectory);
        if (!string.IsNullOrWhiteSpace(path))
        {
            await LoadAudioSourceAsync(path, "手动选择");
        }
    }

    private async Task UseSelectedJobAsAudioInputAsync()
    {
        if (SelectedJob is not null)
        {
            await LoadAudioSourceAsync(SelectedJob.InputPath, "当前选中任务");
        }
    }

    private async Task ChooseClipInputAsync()
    {
        var path = _userDialogService.PickMediaFile(Settings.InputDirectory);
        if (!string.IsNullOrWhiteSpace(path))
        {
            await LoadClipSourceAsync(path, "手动选择");
        }
    }

    private async Task UseSelectedJobAsClipInputAsync()
    {
        if (SelectedJob is not null)
        {
            await LoadClipSourceAsync(SelectedJob.InputPath, "当前选中任务");
        }
    }

    private void ChooseSelectedJobDanmaku()
    {
        if (SelectedJob is null)
        {
            return;
        }

        var initialDirectory = File.Exists(SelectedJob.DanmakuInputPath)
            ? Path.GetDirectoryName(SelectedJob.DanmakuInputPath)
            : Path.GetDirectoryName(SelectedJob.InputPath);
        var path = _userDialogService.PickDanmakuFile(initialDirectory);
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        SelectedJob.DanmakuInputPath = path;
        SelectedJob.DanmakuSourceSummary = $"已绑定本地弹幕 | {Path.GetFileName(path)}";
        SelectedJob.DanmakuPreparationSummary = "本地弹幕已变更，请刷新预览";
        SelectedJob.DanmakuXmlPath = string.Empty;
        SelectedJob.DanmakuAssPath = string.Empty;
        SelectedJob.DanmakuXmlCommentCount = 0;
        SelectedJob.DanmakuKeptCommentCount = 0;
        SelectedJob.DanmakuExcludedCommentKeys = string.Empty;
        SelectedDanmakuComments.Clear();
        EditableSelectedDanmakuComments.Clear();
        RaisePropertyChanged(nameof(HasSelectedDanmakuComments));
        RaisePropertyChanged(nameof(HasEditableSelectedDanmakuComments));
        RaisePropertyChanged(nameof(SelectedDanmakuDisabledCount));
        SelectedPreviewImagePath = string.Empty;
        SelectedPreviewSummary = "本地弹幕已变更，请刷新叠加预览";
        SelectedDanmakuAnalysisSummary = "本地弹幕已变更，请重新分析";
        DanmakuSearchText = string.Empty;
        DanmakuKeywordBatchText = string.Empty;
        SelectedDanmakuModeFilter = "all";
        NotifyCommandStateChanged();
    }

    private void ClearSelectedJobDanmaku()
    {
        if (SelectedJob is null)
        {
            return;
        }

        SelectedJob.DanmakuInputPath = string.Empty;
        SelectedJob.DanmakuSourceSummary = string.Empty;
        SelectedJob.DanmakuPreparationSummary = string.Empty;
        SelectedJob.DanmakuXmlPath = string.Empty;
        SelectedJob.DanmakuAssPath = string.Empty;
        SelectedJob.DanmakuXmlCommentCount = 0;
        SelectedJob.DanmakuKeptCommentCount = 0;
        SelectedJob.DanmakuExcludedCommentKeys = string.Empty;
        SelectedDanmakuComments.Clear();
        EditableSelectedDanmakuComments.Clear();
        RaisePropertyChanged(nameof(HasSelectedDanmakuComments));
        RaisePropertyChanged(nameof(HasEditableSelectedDanmakuComments));
        RaisePropertyChanged(nameof(SelectedDanmakuDisabledCount));
        SelectedPreviewImagePath = string.Empty;
        SelectedPreviewSummary = "已清空本地弹幕绑定";
        SelectedDanmakuAnalysisSummary = "已清空当前任务的弹幕分析";
        DanmakuSearchText = string.Empty;
        DanmakuKeywordBatchText = string.Empty;
        SelectedDanmakuModeFilter = "all";
        NotifyCommandStateChanged();
    }

    private void OpenSelectedDanmaku()
    {
        if (SelectedJob is not null && File.Exists(SelectedJob.DanmakuInputPath))
        {
            _userDialogService.OpenFile(SelectedJob.DanmakuInputPath);
        }
    }

    private void OpenGeneratedDanmakuAss()
    {
        if (SelectedJob is not null && File.Exists(SelectedJob.DanmakuAssPath))
        {
            _userDialogService.OpenFile(SelectedJob.DanmakuAssPath);
        }
    }

    private async Task AnalyzeSelectedDanmakuAsync()
    {
        if (SelectedJob is null || !File.Exists(SelectedJob.InputPath))
        {
            return;
        }

        var probe = await _nativeMediaCoreService.ProbeMediaAsync(SelectedJob.InputPath, CancellationToken.None)
            ?? await _ffprobeService.ProbeAsync(SelectedJob.InputPath, CancellationToken.None);

        if (probe is null)
        {
            SelectedDanmakuAnalysisSummary = "媒体分析失败，无法分析弹幕";
            StatusMessage = "弹幕分析失败";
            return;
        }

        SelectedJob.SourceDurationSeconds = probe.Duration.TotalSeconds;
        SelectedDanmakuAnalysisSummary = "正在重新分析当前任务的弹幕";
        StatusMessage = "正在分析弹幕";

        var overlay = await PrepareOverlayAssetsAsync(SelectedJob, probe, CancellationToken.None);
        if (!overlay.Success)
        {
            SelectedDanmakuAnalysisSummary = overlay.ErrorMessage;
            StatusMessage = "弹幕分析失败";
            return;
        }

        ApplyOverlayStateToJob(SelectedJob, overlay);
        await RefreshSelectedDanmakuAnalysisAsync(SelectedJob, overlay);
        SelectedPreviewSummary = "弹幕分析已更新，可继续刷新叠加预览";
        SelectedPreviewImagePath = string.Empty;
        StatusMessage = "弹幕分析已更新";
        NotifyCommandStateChanged();
    }

    private void ClearSelectedDanmakuExclusions()
    {
        if (SelectedJob is null)
        {
            return;
        }

        SelectedJob.DanmakuExcludedCommentKeys = string.Empty;
        foreach (var comment in EditableSelectedDanmakuComments)
        {
            comment.IsEnabled = true;
        }

        SelectedPreviewImagePath = string.Empty;
        SelectedPreviewSummary = "已清空手动禁用弹幕，请重新分析或刷新预览";
        SelectedDanmakuAnalysisSummary = "已清空手动禁用弹幕，请重新分析以查看最新统计。";
        RaisePropertyChanged(nameof(SelectedDanmakuDisabledCount));
        NotifyCommandStateChanged();
    }

    private async Task ImportSelectedDanmakuRulesAsync()
    {
        if (SelectedJob is null)
        {
            return;
        }

        var initialDirectory = File.Exists(SelectedJob.DanmakuInputPath)
            ? Path.GetDirectoryName(SelectedJob.DanmakuInputPath)
            : Settings.OutputDirectory;
        var path = _userDialogService.PickFile(
            "导入弹幕禁用规则",
            "规则文件 (*.json;*.txt)|*.json;*.txt|JSON 文件 (*.json)|*.json|文本文件 (*.txt)|*.txt|所有文件 (*.*)|*.*",
            initialDirectory);
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        var excludedCommentKeys = await _danmakuExclusionRuleService.ImportAsync(path);
        SelectedJob.DanmakuExcludedCommentKeys = string.Join(Environment.NewLine, excludedCommentKeys.OrderBy(key => key, StringComparer.Ordinal));
        SelectedPreviewImagePath = string.Empty;
        SelectedPreviewSummary = "已导入禁用规则，请重新分析或刷新预览";
        SelectedDanmakuAnalysisSummary = $"已导入 {excludedCommentKeys.Count} 条手动禁用规则。";
        AppendLog($"已导入弹幕禁用规则：{path} | 条数：{excludedCommentKeys.Count}");

        if (!string.IsNullOrWhiteSpace(SelectedJob.DanmakuXmlPath) && File.Exists(SelectedJob.DanmakuXmlPath))
        {
            await AnalyzeSelectedDanmakuAsync();
        }
        else
        {
            NotifyCommandStateChanged();
        }
    }

    private async Task ExportSelectedDanmakuRulesAsync()
    {
        if (SelectedJob is null)
        {
            return;
        }

        var excludedCommentKeys = ParseExcludedCommentKeys(SelectedJob)
            .OrderBy(key => key, StringComparer.Ordinal)
            .ToList();
        var defaultExtension = ".json";
        var defaultName = $"{Path.GetFileNameWithoutExtension(SelectedJob.InputPath)}-danmaku-rules{defaultExtension}";
        var savePath = _userDialogService.PickSaveFile(
            "导出弹幕禁用规则",
            "JSON 文件 (*.json)|*.json|文本文件 (*.txt)|*.txt",
            defaultName,
            Settings.OutputDirectory);
        if (string.IsNullOrWhiteSpace(savePath))
        {
            return;
        }

        await _danmakuExclusionRuleService.ExportAsync(savePath, SelectedJob, excludedCommentKeys);
        StatusMessage = $"弹幕禁用规则已导出：{savePath}";
        AppendLog($"已导出弹幕禁用规则：{savePath} | 条数：{excludedCommentKeys.Count}");
    }

    private void SetFilteredDanmakuEnabled(bool isEnabled)
    {
        if (SelectedJob is null)
        {
            return;
        }

        var visibleComments = EditableSelectedDanmakuCommentsView
            .Cast<object>()
            .OfType<EditableDanmakuComment>()
            .ToList();

        if (visibleComments.Count == 0)
        {
            return;
        }

        _suppressDanmakuToggleSync = true;
        try
        {
            foreach (var comment in visibleComments)
            {
                comment.IsEnabled = isEnabled;
            }
        }
        finally
        {
            _suppressDanmakuToggleSync = false;
        }

        var excludedCommentKeys = EditableSelectedDanmakuComments
            .Where(comment => !comment.IsEnabled)
            .Select(comment => comment.Key)
            .OrderBy(key => key, StringComparer.Ordinal)
            .ToList();
        SelectedJob.DanmakuExcludedCommentKeys = string.Join(Environment.NewLine, excludedCommentKeys);
        SelectedPreviewImagePath = string.Empty;
        SelectedPreviewSummary = "批量禁用列表已更新，请重新分析或刷新预览";
        SelectedDanmakuAnalysisSummary = isEnabled
            ? $"已恢复当前筛选命中的 {visibleComments.Count} 条弹幕。"
            : $"已禁用当前筛选命中的 {visibleComments.Count} 条弹幕。";
        RaisePropertyChanged(nameof(SelectedDanmakuDisabledCount));
        RaisePropertyChanged(nameof(FilteredDanmakuCountSummary));
        NotifyCommandStateChanged();
    }

    private void SetKeywordMatchedDanmakuEnabled(bool isEnabled)
    {
        var keywords = ParseKeywordBatchInput(DanmakuKeywordBatchText);
        if (SelectedJob is null || keywords.Count == 0)
        {
            SelectedDanmakuAnalysisSummary = "请先填写关键词，每行一个或用 | 分隔。";
            return;
        }

        var matchedComments = EditableSelectedDanmakuComments
            .Where(comment => keywords.Any(keyword => comment.Content.Contains(keyword, StringComparison.OrdinalIgnoreCase)))
            .ToList();
        if (matchedComments.Count == 0)
        {
            SelectedDanmakuAnalysisSummary = "没有弹幕命中当前关键词。";
            return;
        }

        _suppressDanmakuToggleSync = true;
        try
        {
            foreach (var comment in matchedComments)
            {
                comment.IsEnabled = isEnabled;
            }
        }
        finally
        {
            _suppressDanmakuToggleSync = false;
        }

        var excludedCommentKeys = EditableSelectedDanmakuComments
            .Where(comment => !comment.IsEnabled)
            .Select(comment => comment.Key)
            .OrderBy(key => key, StringComparer.Ordinal)
            .ToList();
        SelectedJob.DanmakuExcludedCommentKeys = string.Join(Environment.NewLine, excludedCommentKeys);
        SelectedPreviewImagePath = string.Empty;
        SelectedPreviewSummary = "关键词批量规则已更新，请重新分析或刷新预览";
        SelectedDanmakuAnalysisSummary = isEnabled
            ? $"已恢复关键词命中的 {matchedComments.Count} 条弹幕。"
            : $"已禁用关键词命中的 {matchedComments.Count} 条弹幕。";
        RaisePropertyChanged(nameof(SelectedDanmakuDisabledCount));
        NotifyCommandStateChanged();
    }

    private void ChoosePipOverlay()
    {
        var initialDirectory = string.IsNullOrWhiteSpace(PipOverlayPath)
            ? Settings.InputDirectory
            : Path.GetDirectoryName(PipOverlayPath);
        var path = _userDialogService.PickMediaFile(initialDirectory);
        if (!string.IsNullOrWhiteSpace(path))
        {
            PipOverlayPath = path;
            StatusMessage = $"已选择画中画素材：{Path.GetFileName(path)}";
            AppendLog($"已选择画中画素材：{path}");
        }
    }

    private void ClearPipOverlay()
    {
        PipOverlayPath = string.Empty;
        StatusMessage = "已清空画中画素材";
    }

    private void ChooseAudioMixBackground()
    {
        var initialDirectory = string.IsNullOrWhiteSpace(AudioMixBackgroundPath)
            ? Settings.InputDirectory
            : Path.GetDirectoryName(AudioMixBackgroundPath);
        var path = _userDialogService.PickMediaFile(initialDirectory);
        if (!string.IsNullOrWhiteSpace(path))
        {
            AudioMixBackgroundPath = path;
            StatusMessage = $"已选择混音 BGM：{Path.GetFileName(path)}";
            AppendLog($"已选择混音 BGM：{path}");
        }
    }

    private void ClearAudioMixBackground()
    {
        AudioMixBackgroundPath = string.Empty;
        StatusMessage = "已清空混音 BGM";
    }

    private async Task LoadAudioSourceAsync(string inputPath, string sourceLabel)
    {
        if (!File.Exists(inputPath))
        {
            StatusMessage = "音频源文件不存在";
            AudioStatusMessage = "音频源文件不存在";
            AudioProbeSummary = "请选择有效的媒体文件";
            return;
        }

        AudioInputPath = inputPath;
        AudioStatusMessage = "正在分析音轨";
        AudioProbeSummary = "正在读取媒体信息";
        AudioProgress = 0;
        AudioSpeed = string.Empty;
        AudioTracks.Clear();
        SilenceSegments.Clear();
        AudioSilenceSummary = "尚未执行静音检测";
        SelectedAudioTrack = null;
        _audioSourceDuration = TimeSpan.Zero;
        RaisePropertyChanged(nameof(AudioSourceDurationText));
        RefreshAudioOutputPathPreview();
        RefreshAudioMixOutputPathPreview();
        NotifyCommandStateChanged();

        try
        {
            AppendLog($"开始分析音频源：{inputPath} | 来源：{sourceLabel}");
            var probe = await _nativeMediaCoreService.ProbeMediaAsync(inputPath)
                ?? await _ffprobeService.ProbeAsync(inputPath);

            if (probe is null)
            {
                AudioStatusMessage = "媒体分析失败";
                AudioProbeSummary = "ffprobe 未返回可用结果";
                StatusMessage = "音频源分析失败";
                return;
            }

            _audioSourceDuration = probe.Duration;
            RaisePropertyChanged(nameof(AudioSourceDurationText));

            foreach (var track in probe.AudioTracks)
            {
                AudioTracks.Add(track);
            }

            SelectedAudioTrack = AudioTracks.FirstOrDefault(track => track.IsDefault)
                ?? AudioTracks.FirstOrDefault();

            AudioProbeSummary = AudioTracks.Count == 0
                ? $"未检测到可提取音轨 | 时长 {FormatTimeSpan(probe.Duration)} | 来源 {probe.AnalysisSource}"
                : $"已检测到 {AudioTracks.Count} 条音轨 | 时长 {FormatTimeSpan(probe.Duration)} | 来源 {probe.AnalysisSource}";

            AudioStatusMessage = AudioTracks.Count == 0
                ? "该媒体没有可提取的音轨"
                : $"已就绪，当前选择：{SelectedAudioTrack!.Summary}";

            StatusMessage = $"音频源已载入：{Path.GetFileName(inputPath)}";
            AppendLog($"音频源分析完成：{AudioProbeSummary}");
            OnAudioSourceLoaded(inputPath);
        }
        catch (Exception ex)
        {
            AudioTracks.Clear();
            SelectedAudioTrack = null;
            _audioSourceDuration = TimeSpan.Zero;
            RaisePropertyChanged(nameof(AudioSourceDurationText));
            AudioProbeSummary = $"媒体分析失败：{ex.Message}";
            AudioStatusMessage = "音轨分析失败";
            StatusMessage = "音频源分析失败";
            AppendLog($"音频源分析失败：{inputPath} | {ex.Message}");
        }
        finally
        {
            NotifyCommandStateChanged();
        }
    }

    private async Task LoadClipSourceAsync(string inputPath, string sourceLabel)
    {
        if (!File.Exists(inputPath))
        {
            StatusMessage = "裁剪源文件不存在";
            ClipStatusMessage = "裁剪源文件不存在";
            ClipProbeSummary = "请选择有效的媒体文件";
            return;
        }

        ClipInputPath = inputPath;
        ClipStatusMessage = "正在分析媒体时长";
        ClipProbeSummary = "正在读取媒体信息";
        ClipProgress = 0;
        ClipSpeed = string.Empty;
        SceneCutPoints.Clear();
        SceneDetectionSummary = "尚未执行场景检测";
        AutoSegmentSummary = "尚未生成自动分段";
        BlackSegments.Clear();
        FreezeSegments.Clear();
        BlackDetectSummary = "尚未执行黑场检测";
        FreezeDetectSummary = "尚未执行冻帧检测";
        CoverCandidates.Clear();
        CoverCandidatesSummary = "尚未生成封面候选";
        CoverCandidatesDirectory = string.Empty;
        DouyinProgress = 0;
        DouyinSpeed = string.Empty;
        DouyinStatusMessage = "正在分析媒体信息";
        DouyinSubtitleSummary = "正在分析字幕";
        _douyinSubtitleStreamOrdinal = null;
        _clipHasAudio = false;
        _clipSourceDuration = TimeSpan.Zero;
        RaisePropertyChanged(nameof(ClipSourceDurationText));
        RefreshClipOutputPathPreview();
        RefreshConcatOutputPathPreview();
        RefreshVerticalOutputPathPreview();
        RefreshGifOutputPathPreview();
        RefreshPipOutputPathPreview();
        RefreshSpeedOutputPathPreview();
        RefreshReverseOutputPathPreview();
        RefreshDouyinOutputPathPreview();
        RefreshConcatSegmentsPreview();
        NotifyCommandStateChanged();

        try
        {
            AppendLog($"开始分析裁剪源：{inputPath} | 来源：{sourceLabel}");
            var probe = await _nativeMediaCoreService.ProbeMediaAsync(inputPath)
                ?? await _ffprobeService.ProbeAsync(inputPath);

            if (probe is null)
            {
                ClipStatusMessage = "媒体分析失败";
                ClipProbeSummary = "ffprobe 未返回可用结果";
                StatusMessage = "裁剪源分析失败";
                return;
            }

            _clipSourceDuration = probe.Duration;
            _clipHasAudio = probe.AudioTracks.Count > 0;
            RaisePropertyChanged(nameof(ClipSourceDurationText));
            ClipProbeSummary = $"媒体时长 {FormatTimeSpan(probe.Duration)} | 音频 {(_clipHasAudio ? "主音轨可用" : "无音轨")} | 来源 {probe.AnalysisSource}";
            ClipStatusMessage = "已就绪，可开始裁剪、拼接或竖屏适配";
            var nativeAnalysis = await _nativeMediaCoreService.AnalyzeSubtitlesAsync(
                inputPath,
                probe.SubtitleTracks);
            var subtitleTracks = nativeAnalysis.SubtitleTracks;
            var selectedSubtitleOrdinal = _subtitleSelectionService.SelectSubtitleTrackOrdinal(
                subtitleTracks,
                Settings.SubtitlePreference);
            var selectedSubtitleTrack = selectedSubtitleOrdinal is not null && selectedSubtitleOrdinal.Value < subtitleTracks.Count
                ? subtitleTracks[selectedSubtitleOrdinal.Value]
                : null;
            _douyinSubtitleStreamOrdinal = selectedSubtitleTrack?.IsTextBased == true
                ? selectedSubtitleOrdinal
                : null;
            DouyinSubtitleSummary = _douyinSubtitleStreamOrdinal is null
                ? "未找到可自动烧录的文本字幕，将输出无字幕版本"
                : $"已自动选择字幕轨 #{_douyinSubtitleStreamOrdinal.Value} | 来源 {nativeAnalysis.Source}";
            DouyinStatusMessage = _clipHasAudio ? "已就绪，可开始抖音直出" : "源文件无音轨，如需导出请提供 BGM";
            RefreshConcatSegmentsPreview();
            StatusMessage = $"裁剪源已载入：{Path.GetFileName(inputPath)}";
            AppendLog($"裁剪源分析完成：{ClipProbeSummary}");
        }
        catch (Exception ex)
        {
            _clipHasAudio = false;
            _clipSourceDuration = TimeSpan.Zero;
            RaisePropertyChanged(nameof(ClipSourceDurationText));
            ClipProbeSummary = $"媒体分析失败：{ex.Message}";
            ClipStatusMessage = "裁剪源分析失败";
            DouyinStatusMessage = "抖音直出源分析失败";
            DouyinSubtitleSummary = "字幕分析失败";
            RefreshConcatSegmentsPreview();
            StatusMessage = "裁剪源分析失败";
            AppendLog($"裁剪源分析失败：{inputPath} | {ex.Message}");
        }
        finally
        {
            NotifyCommandStateChanged();
        }
    }

    private void RemoveSelectedJob()
    {
        if (SelectedJob is null)
        {
            return;
        }

        var job = SelectedJob;
        SelectedJob = null;
        DetachJob(job);
        Jobs.Remove(job);
    }

    private void RetryFailedJobs()
    {
        foreach (var job in Jobs.Where(job => job.Status is JobStatus.Failed or JobStatus.Cancelled))
        {
            job.Status = JobStatus.Pending;
            job.Progress = 0;
            job.Speed = string.Empty;
            job.Message = "已重新加入队列";
        }

        StatusMessage = "已重置失败/取消任务，可重新开始转码";
        AppendLog("已将失败或取消的任务重新加入队列。");
        RaiseQueueSummaryProperties();
        NotifyCommandStateChanged();
    }

    private void ClearFinishedJobs()
    {
        var removableJobs = Jobs
            .Where(job => job.Status is JobStatus.Success or JobStatus.Skipped or JobStatus.Cancelled)
            .ToList();

        foreach (var job in removableJobs)
        {
            DetachJob(job);
            Jobs.Remove(job);
        }

        StatusMessage = $"已清理 {removableJobs.Count} 个已结束任务";
        AppendLog($"已从队列中移除 {removableJobs.Count} 个已结束任务。");
        RaiseQueueSummaryProperties();
        NotifyCommandStateChanged();
    }

    private void OpenSelectedOutputDirectory()
    {
        if (SelectedJob is null || string.IsNullOrWhiteSpace(SelectedJob.OutputPath))
        {
            return;
        }

        var directoryPath = Path.GetDirectoryName(SelectedJob.OutputPath);
        if (!string.IsNullOrWhiteSpace(directoryPath))
        {
            _userDialogService.OpenFolder(directoryPath);
        }
    }

    private async Task CaptureSelectedFrameAsync()
    {
        if (SelectedJob is null || !File.Exists(SelectedJob.InputPath))
        {
            StatusMessage = "选中任务的源文件不存在";
            return;
        }

        var timeSeconds = DetermineFrameSampleTimeSeconds(SelectedJob);
        var sampleDirectory = Path.Combine(Settings.OutputDirectory, "frame_samples");
        var fileName = $"{Path.GetFileNameWithoutExtension(SelectedJob.InputPath)}-{timeSeconds:0.000}s.png";
        var outputPath = Path.Combine(sampleDirectory, fileName);

        AppendLog($"开始导出诊断截图：{SelectedJob.FileName} @ {timeSeconds:0.000}s");
        var result = await _nativeMediaCoreService.CaptureFrameAsync(SelectedJob.InputPath, outputPath, timeSeconds);

        if (result.Success)
        {
            StatusMessage = $"诊断截图已导出：{result.OutputPath}";
            AppendLog($"诊断截图已导出：{result.OutputPath} | 来源：{result.Source}");
            return;
        }

        StatusMessage = "诊断截图导出失败";
        AppendLog($"诊断截图导出失败：{result.Message}");
    }

    private async Task CaptureSelectedFrameSetAsync()
    {
        if (SelectedJob is null || !File.Exists(SelectedJob.InputPath))
        {
            StatusMessage = "选中任务的源文件不存在";
            return;
        }

        var sampleTimes = DetermineInspectionSampleTimes(SelectedJob);
        var sampleDirectory = Path.Combine(Settings.OutputDirectory, "frame_samples", Path.GetFileNameWithoutExtension(SelectedJob.InputPath));
        var filePrefix = Path.GetFileNameWithoutExtension(SelectedJob.InputPath);

        AppendLog($"开始导出巡检三连图：{SelectedJob.FileName} @ {string.Join(", ", sampleTimes.Select(time => $"{time:0.000}s"))}");
        var result = await _nativeMediaCoreService.CaptureDiagnosticFramesAsync(
            SelectedJob.InputPath,
            sampleDirectory,
            filePrefix,
            sampleTimes);

        if (result.Success)
        {
            var inspectionReport = await _frameInspectionService.AnalyzeAsync(
                SelectedJob.InputPath,
                result.OutputDirectory,
                result.Source,
                result.Samples);

            StatusMessage = $"巡检截图已导出：{result.OutputDirectory}";
            AppendLog($"巡检截图已导出：{result.OutputDirectory} | 来源：{result.Source} | 数量：{result.Samples.Count}");
            InspectionSamples.Clear();
            foreach (var sample in inspectionReport.Samples.Where(sample => sample.OutputExists))
            {
                InspectionSamples.Add(sample);
            }
            _inspectionReport = inspectionReport;
            _inspectionOutputDirectory = result.OutputDirectory;
            _inspectionSource = result.Source;
            _inspectionSummary = inspectionReport.Summary;
            AppendLog($"巡检自动分析完成：{inspectionReport.Summary}");
            RaiseInspectionProperties();
            NotifyCommandStateChanged();
            return;
        }

        StatusMessage = "巡检截图导出失败";
        AppendLog($"巡检截图导出失败：{result.Message}");
        _inspectionReport = null;
        _inspectionSummary = $"巡检截图导出失败：{result.Message}";
        RaiseInspectionProperties();
    }

    private async Task SaveSettingsAsync()
    {
        await _settingsService.SaveAsync(Settings);
        StatusMessage = "设置已保存";
        AppendLog($"已保存设置到：{_settingsService.SettingsPath}");
    }

    private async Task ExtractAudioAsync()
    {
        if (!CanExtractAudio())
        {
            return;
        }

        if (!TryParseOptionalTimeSpan(AudioStartTimeText, out var startTime))
        {
            AudioStatusMessage = "开始时间格式无效，请使用 hh:mm:ss 或秒数";
            StatusMessage = "音频提取参数无效";
            return;
        }

        if (!TryParseOptionalTimeSpan(AudioDurationText, out var duration))
        {
            AudioStatusMessage = "截取时长格式无效，请使用 hh:mm:ss 或秒数";
            StatusMessage = "音频提取参数无效";
            return;
        }

        if (startTime is { } parsedStart && parsedStart < TimeSpan.Zero)
        {
            AudioStatusMessage = "开始时间不能小于 0";
            StatusMessage = "音频提取参数无效";
            return;
        }

        if (duration is { } parsedDuration && parsedDuration <= TimeSpan.Zero)
        {
            AudioStatusMessage = "截取时长必须大于 0";
            StatusMessage = "音频提取参数无效";
            return;
        }

        var effectiveStart = startTime ?? TimeSpan.Zero;
        if (_audioSourceDuration > TimeSpan.Zero)
        {
            if (effectiveStart >= _audioSourceDuration)
            {
                AudioStatusMessage = "开始时间超出媒体总时长";
                StatusMessage = "音频提取参数无效";
                return;
            }

            if (duration.HasValue && effectiveStart + duration.Value > _audioSourceDuration)
            {
                AudioStatusMessage = "截取区间超出媒体总时长";
                StatusMessage = "音频提取参数无效";
                return;
            }
        }

        var totalDurationSeconds = duration?.TotalSeconds
            ?? (_audioSourceDuration > TimeSpan.Zero
                ? Math.Max((_audioSourceDuration - effectiveStart).TotalSeconds, 0d)
                : 0d);

        RefreshAudioOutputPathPreview();
        AudioProgress = 0;
        AudioSpeed = string.Empty;
        IsAudioExtracting = true;
        _audioExtractionCancellationTokenSource = new CancellationTokenSource();
        var outputPath = AudioOutputPathPreview;
        var formatLabel = AudioCommandBuilder.GetDisplayName(SelectedAudioFormat, AudioNormalize);

        AudioStatusMessage = $"正在提取为 {formatLabel}";
        StatusMessage = "正在提取音频";
        AppendLog($"开始提取音频：{AudioInputPath} -> {outputPath} | 格式 {formatLabel}");

        try
        {
            var result = await _audioProcessingWorkflow.ExtractAsync(
                AudioInputPath,
                outputPath,
                SelectedAudioFormat,
                SelectedAudioTrack?.Index,
                startTime,
                duration,
                AudioNormalize,
                Settings.AudioBitrateKbps,
                totalDurationSeconds,
                new Progress<WorkflowProgress>(OnAudioWorkflowProgress),
                _audioExtractionCancellationTokenSource.Token);

            if (result.Success)
            {
                AudioProgress = 100;
                AudioSpeed = "done";
                AudioStatusMessage = $"提取完成：{Path.GetFileName(result.OutputPath)}";
                StatusMessage = "音频提取完成";
                AppendLog($"音频提取完成：{result.OutputPath}");
                return;
            }

            if (string.Equals(result.ErrorMessage, "已取消", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(result.ErrorMessage, "Cancelled", StringComparison.OrdinalIgnoreCase))
            {
                AudioStatusMessage = "音频提取已取消";
                StatusMessage = "音频提取已取消";
                AppendLog("音频提取已取消。");
                return;
            }

            AudioStatusMessage = $"提取失败：{result.ErrorMessage}";
            StatusMessage = "音频提取失败";
            AppendLog($"音频提取失败：{result.ErrorMessage}");
        }
        finally
        {
            IsAudioExtracting = false;
            _audioExtractionCancellationTokenSource?.Dispose();
            _audioExtractionCancellationTokenSource = null;
        }
    }

    private async Task DetectSilenceAsync()
    {
        if (!CanDetectSilence())
        {
            return;
        }

        if (!double.TryParse(AudioSilenceThresholdText, NumberStyles.Float, CultureInfo.InvariantCulture, out var threshold) &&
            !double.TryParse(AudioSilenceThresholdText, NumberStyles.Float, CultureInfo.CurrentCulture, out threshold))
        {
            AudioSilenceSummary = "静音阈值格式无效";
            AudioStatusMessage = "静音检测参数无效";
            StatusMessage = "静音检测参数无效";
            return;
        }

        if (!double.TryParse(AudioSilenceMinimumDurationText, NumberStyles.Float, CultureInfo.InvariantCulture, out var minimumDuration) &&
            !double.TryParse(AudioSilenceMinimumDurationText, NumberStyles.Float, CultureInfo.CurrentCulture, out minimumDuration))
        {
            AudioSilenceSummary = "最短静音时长格式无效";
            AudioStatusMessage = "静音检测参数无效";
            StatusMessage = "静音检测参数无效";
            return;
        }

        if (minimumDuration <= 0)
        {
            AudioSilenceSummary = "最短静音时长必须大于 0";
            AudioStatusMessage = "静音检测参数无效";
            StatusMessage = "静音检测参数无效";
            return;
        }

        SilenceSegments.Clear();
        IsAudioSilenceDetecting = true;
        AudioStatusMessage = "正在检测静音区间";
        AudioSilenceSummary = $"正在分析阈值 {threshold:0.###} dB、最短 {minimumDuration:0.###} 秒";
        StatusMessage = "正在检测静音区间";
        AppendLog($"开始静音检测：{AudioInputPath} | 阈值 {threshold:0.###}dB | 最短 {minimumDuration:0.###}s");

        try
        {
            var segments = await _audioProcessingWorkflow.DetectSilenceAsync(
                AudioInputPath,
                SelectedAudioTrack?.Index,
                threshold,
                minimumDuration,
                new Progress<WorkflowProgress>(OnAudioWorkflowProgress),
                CancellationToken.None);

            foreach (var segment in segments)
            {
                SilenceSegments.Add(segment);
            }

            AudioSilenceSummary = segments.Count == 0
                ? "未检测到符合条件的静音区间"
                : $"检测到 {segments.Count} 段静音，总静音时长 {segments.Sum(segment => segment.DurationSeconds):0.###} 秒";
            AudioStatusMessage = "静音检测完成";
            StatusMessage = "静音检测完成";
            AppendLog($"静音检测完成：{AudioSilenceSummary}");
        }
        catch (Exception ex)
        {
            AudioSilenceSummary = $"静音检测失败：{ex.Message}";
            AudioStatusMessage = "静音检测失败";
            StatusMessage = "静音检测失败";
            AppendLog($"静音检测失败：{ex.Message}");
        }
        finally
        {
            IsAudioSilenceDetecting = false;
        }
    }

    private async Task StartAudioMixAsync()
    {
        if (!CanStartAudioMix())
        {
            return;
        }

        if (!TryParseOptionalTimeSpan(AudioStartTimeText, out var startTime))
        {
            AudioStatusMessage = "开始时间格式无效，请使用 hh:mm:ss 或秒数";
            StatusMessage = "音频混音参数无效";
            return;
        }

        if (!TryParseOptionalTimeSpan(AudioDurationText, out var duration))
        {
            AudioStatusMessage = "截取时长格式无效，请使用 hh:mm:ss 或秒数";
            StatusMessage = "音频混音参数无效";
            return;
        }

        if (!TryParsePositiveDouble(AudioMixSourceVolumeText, out var sourceVolume) || sourceVolume > 2)
        {
            AudioStatusMessage = "主音量格式无效，范围建议 0.01 - 2.0";
            StatusMessage = "音频混音参数无效";
            return;
        }

        if (!TryParsePositiveDouble(AudioMixBackgroundVolumeText, out var backgroundVolume) || backgroundVolume > 2)
        {
            AudioStatusMessage = "BGM 音量格式无效，范围建议 0.01 - 2.0";
            StatusMessage = "音频混音参数无效";
            return;
        }

        if (startTime is { } parsedStart && parsedStart < TimeSpan.Zero)
        {
            AudioStatusMessage = "开始时间不能小于 0";
            StatusMessage = "音频混音参数无效";
            return;
        }

        if (duration is { } parsedDuration && parsedDuration <= TimeSpan.Zero)
        {
            AudioStatusMessage = "截取时长必须大于 0";
            StatusMessage = "音频混音参数无效";
            return;
        }

        var effectiveStart = startTime ?? TimeSpan.Zero;
        if (_audioSourceDuration > TimeSpan.Zero)
        {
            if (effectiveStart >= _audioSourceDuration)
            {
                AudioStatusMessage = "开始时间超出媒体总时长";
                StatusMessage = "音频混音参数无效";
                return;
            }

            if (duration.HasValue && effectiveStart + duration.Value > _audioSourceDuration)
            {
                AudioStatusMessage = "截取区间超出媒体总时长";
                StatusMessage = "音频混音参数无效";
                return;
            }
        }

        var totalDurationSeconds = duration?.TotalSeconds
            ?? (_audioSourceDuration > TimeSpan.Zero
                ? Math.Max((_audioSourceDuration - effectiveStart).TotalSeconds, 0d)
                : 0d);

        RefreshAudioMixOutputPathPreview();
        AudioProgress = 0;
        AudioSpeed = string.Empty;
        IsAudioExtracting = true;
        _audioExtractionCancellationTokenSource = new CancellationTokenSource();
        var outputPath = AudioMixOutputPathPreview;

        AudioStatusMessage = "正在混合主音轨与 BGM";
        StatusMessage = "正在执行音频混音";
        AppendLog($"开始音频混音：{AudioInputPath} + {AudioMixBackgroundPath} -> {outputPath} | 主音量 {sourceVolume:0.###} | BGM 音量 {backgroundVolume:0.###}");

        try
        {
            var result = await _audioExtractionService.MixAsync(
                AudioInputPath,
                AudioMixBackgroundPath,
                outputPath,
                SelectedAudioTrack?.Index,
                startTime,
                duration,
                AudioNormalize,
                Settings.AudioBitrateKbps,
                totalDurationSeconds,
                sourceVolume,
                backgroundVolume,
                (progress, speed) =>
                {
                    _ = System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
                    {
                        AudioProgress = Math.Round(progress, 2);
                        if (!string.IsNullOrWhiteSpace(speed) && !string.Equals(speed, "done", StringComparison.OrdinalIgnoreCase))
                        {
                            AudioSpeed = speed;
                        }
                    });
                },
                _audioExtractionCancellationTokenSource.Token);

            if (result.Success)
            {
                AudioProgress = 100;
                AudioSpeed = "done";
                AudioStatusMessage = $"混音完成：{Path.GetFileName(result.OutputPath)}";
                StatusMessage = "音频混音完成";
                AppendLog($"音频混音完成：{result.OutputPath}");
                return;
            }

            if (string.Equals(result.ErrorMessage, "已取消", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(result.ErrorMessage, "Cancelled", StringComparison.OrdinalIgnoreCase))
            {
                AudioStatusMessage = "音频混音已取消";
                StatusMessage = "音频混音已取消";
                AppendLog("音频混音已取消。");
                return;
            }

            AudioStatusMessage = $"混音失败：{result.ErrorMessage}";
            StatusMessage = "音频混音失败";
            AppendLog($"音频混音失败：{result.ErrorMessage}");
        }
        finally
        {
            IsAudioExtracting = false;
            _audioExtractionCancellationTokenSource?.Dispose();
            _audioExtractionCancellationTokenSource = null;
        }
    }

    private async Task StartFastClipAsync()
    {
        if (!CanStartFastClip())
        {
            return;
        }

        if (!TryParseOptionalTimeSpan(ClipStartTimeText, out var startTime) || startTime is null)
        {
            ClipStatusMessage = "开始时间格式无效，请使用 hh:mm:ss 或秒数";
            StatusMessage = "视频裁剪参数无效";
            return;
        }

        if (!TryParseOptionalTimeSpan(ClipDurationText, out var duration) || duration is null)
        {
            ClipStatusMessage = "截取时长格式无效，请使用 hh:mm:ss 或秒数";
            StatusMessage = "视频裁剪参数无效";
            return;
        }

        if (startTime.Value < TimeSpan.Zero)
        {
            ClipStatusMessage = "开始时间不能小于 0";
            StatusMessage = "视频裁剪参数无效";
            return;
        }

        if (duration.Value <= TimeSpan.Zero)
        {
            ClipStatusMessage = "截取时长必须大于 0";
            StatusMessage = "视频裁剪参数无效";
            return;
        }

        if (_clipSourceDuration > TimeSpan.Zero)
        {
            if (startTime.Value >= _clipSourceDuration)
            {
                ClipStatusMessage = "开始时间超出媒体总时长";
                StatusMessage = "视频裁剪参数无效";
                return;
            }

            if (startTime.Value + duration.Value > _clipSourceDuration)
            {
                ClipStatusMessage = "截取区间超出媒体总时长";
                StatusMessage = "视频裁剪参数无效";
                return;
            }
        }

        RefreshClipOutputPathPreview();
        ClipProgress = 0;
        ClipSpeed = string.Empty;
        IsClipRunning = true;
        _clipCancellationTokenSource = new CancellationTokenSource();
        var outputPath = ClipOutputPathPreview;
        var clipModeLabel = SelectedClipMode == ClipMode.Fast ? "无损快切" : "精准裁剪";

        ClipStatusMessage = $"正在执行{clipModeLabel}";
        StatusMessage = $"正在执行{clipModeLabel}";
        AppendLog($"开始{clipModeLabel}：{ClipInputPath} -> {outputPath} | 起点 {FormatTimeSpan(startTime.Value)} | 时长 {FormatTimeSpan(duration.Value)}");

        try
        {
            ClipResult result;
            if (SelectedClipMode == ClipMode.Fast)
            {
                result = await _videoClipService.FastClipAsync(
                    ClipInputPath,
                    outputPath,
                    startTime.Value,
                    duration.Value,
                    (progress, speed) =>
                    {
                        _ = System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
                        {
                            ClipProgress = Math.Round(progress, 2);
                            if (!string.IsNullOrWhiteSpace(speed) && !string.Equals(speed, "done", StringComparison.OrdinalIgnoreCase))
                            {
                                ClipSpeed = speed;
                            }
                        });
                    },
                    _clipCancellationTokenSource.Token);
            }
            else
            {
                var encoder = _hardwareDetectionService.ResolveVideoEncoder(Settings.VideoEncoderMode, _isNvencAvailable);
                result = await _videoClipService.PreciseClipAsync(
                    ClipInputPath,
                    outputPath,
                    startTime.Value,
                    duration.Value,
                    encoder,
                    Settings.NvencPreset,
                    Settings.Cq,
                    Settings.AudioBitrateKbps,
                    (progress, speed) =>
                    {
                        _ = System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
                        {
                            ClipProgress = Math.Round(progress, 2);
                            if (!string.IsNullOrWhiteSpace(speed) && !string.Equals(speed, "done", StringComparison.OrdinalIgnoreCase))
                            {
                                ClipSpeed = speed;
                            }
                        });
                    },
                    _clipCancellationTokenSource.Token);
            }

            if (result.Success)
            {
                ClipProgress = 100;
                ClipSpeed = "done";
                ClipStatusMessage = $"裁剪完成：{Path.GetFileName(result.OutputPath)}";
                StatusMessage = $"{clipModeLabel}完成";
                AppendLog($"{clipModeLabel}完成：{result.OutputPath}");
                return;
            }

            if (string.Equals(result.ErrorMessage, "已取消", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(result.ErrorMessage, "Cancelled", StringComparison.OrdinalIgnoreCase))
            {
                ClipStatusMessage = $"{clipModeLabel}已取消";
                StatusMessage = $"{clipModeLabel}已取消";
                AppendLog($"{clipModeLabel}已取消。");
                return;
            }

            ClipStatusMessage = $"裁剪失败：{result.ErrorMessage}";
            StatusMessage = $"{clipModeLabel}失败";
            AppendLog($"{clipModeLabel}失败：{result.ErrorMessage}");
        }
        finally
        {
            IsClipRunning = false;
            _clipCancellationTokenSource?.Dispose();
            _clipCancellationTokenSource = null;
        }
    }

    private async Task StartGifPreviewAsync()
    {
        if (!CanStartFastClip())
        {
            return;
        }

        if (!TryParseOptionalTimeSpan(ClipStartTimeText, out var startTime) || startTime is null)
        {
            ClipStatusMessage = "开始时间格式无效，请使用 hh:mm:ss 或秒数";
            StatusMessage = "GIF 预览参数无效";
            return;
        }

        if (!TryParseOptionalTimeSpan(ClipDurationText, out var duration) || duration is null)
        {
            ClipStatusMessage = "预览时长格式无效，请使用 hh:mm:ss 或秒数";
            StatusMessage = "GIF 预览参数无效";
            return;
        }

        if (startTime.Value < TimeSpan.Zero || duration.Value <= TimeSpan.Zero)
        {
            ClipStatusMessage = "GIF 预览的开始时间和时长必须有效";
            StatusMessage = "GIF 预览参数无效";
            return;
        }

        if (_clipSourceDuration > TimeSpan.Zero && startTime.Value + duration.Value > _clipSourceDuration)
        {
            ClipStatusMessage = "GIF 预览区间超出媒体总时长";
            StatusMessage = "GIF 预览参数无效";
            return;
        }

        RefreshGifOutputPathPreview();
        ClipProgress = 0;
        ClipSpeed = string.Empty;
        IsClipRunning = true;
        _clipCancellationTokenSource = new CancellationTokenSource();
        var outputPath = GifOutputPathPreview;

        ClipStatusMessage = "正在生成 GIF 预览";
        StatusMessage = "正在生成 GIF 预览";
        AppendLog($"开始生成 GIF 预览：{ClipInputPath} -> {outputPath} | 起点 {FormatTimeSpan(startTime.Value)} | 时长 {FormatTimeSpan(duration.Value)}");

        try
        {
            var result = await _videoClipService.GenerateGifPreviewAsync(
                ClipInputPath,
                outputPath,
                startTime.Value,
                duration.Value,
                (progress, speed) =>
                {
                    _ = System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
                    {
                        ClipProgress = Math.Round(progress, 2);
                        if (!string.IsNullOrWhiteSpace(speed) && !string.Equals(speed, "done", StringComparison.OrdinalIgnoreCase))
                        {
                            ClipSpeed = speed;
                        }
                    });
                },
                _clipCancellationTokenSource.Token);

            if (result.Success)
            {
                ClipProgress = 100;
                ClipSpeed = "done";
                ClipStatusMessage = $"GIF 预览已生成：{Path.GetFileName(result.OutputPath)}";
                StatusMessage = "GIF 预览生成完成";
                AppendLog($"GIF 预览生成完成：{result.OutputPath}");
                return;
            }

            if (string.Equals(result.ErrorMessage, "已取消", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(result.ErrorMessage, "Cancelled", StringComparison.OrdinalIgnoreCase))
            {
                ClipStatusMessage = "GIF 预览生成已取消";
                StatusMessage = "GIF 预览生成已取消";
                AppendLog("GIF 预览生成已取消。");
                return;
            }

            ClipStatusMessage = $"GIF 预览生成失败：{result.ErrorMessage}";
            StatusMessage = "GIF 预览生成失败";
            AppendLog($"GIF 预览生成失败：{result.ErrorMessage}");
        }
        finally
        {
            IsClipRunning = false;
            _clipCancellationTokenSource?.Dispose();
            _clipCancellationTokenSource = null;
        }
    }

    private async Task StartPictureInPictureAsync()
    {
        if (!CanStartPictureInPicture())
        {
            return;
        }

        if (!TryParseUnitInterval(PipScaleText, out var pipScale) || pipScale <= 0 || pipScale >= 1)
        {
            ClipStatusMessage = "画中画缩放比例必须介于 0 到 1 之间";
            StatusMessage = "画中画参数无效";
            return;
        }

        RefreshPipOutputPathPreview();
        ClipProgress = 0;
        ClipSpeed = string.Empty;
        IsClipRunning = true;
        _clipCancellationTokenSource = new CancellationTokenSource();
        var outputPath = PipOutputPathPreview;
        var encoder = _hardwareDetectionService.ResolveVideoEncoder(Settings.VideoEncoderMode, _isNvencAvailable);

        ClipStatusMessage = "正在生成画中画";
        StatusMessage = "正在执行画中画";
        AppendLog($"开始画中画：{ClipInputPath} + {PipOverlayPath} -> {outputPath} | corner={SelectedPipCorner} | scale={pipScale:0.###}");

        try
        {
            var result = await _videoClipService.AddPictureInPictureAsync(
                ClipInputPath,
                PipOverlayPath,
                outputPath,
                SelectedPipCorner,
                pipScale,
                encoder,
                Settings.NvencPreset,
                Settings.Cq,
                Settings.AudioBitrateKbps,
                _clipSourceDuration.TotalSeconds,
                (progress, speed) =>
                {
                    _ = System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
                    {
                        ClipProgress = Math.Round(progress, 2);
                        if (!string.IsNullOrWhiteSpace(speed) && !string.Equals(speed, "done", StringComparison.OrdinalIgnoreCase))
                        {
                            ClipSpeed = speed;
                        }
                    });
                },
                _clipCancellationTokenSource.Token);

            if (result.Success)
            {
                ClipProgress = 100;
                ClipSpeed = "done";
                ClipStatusMessage = $"画中画完成：{Path.GetFileName(result.OutputPath)}";
                StatusMessage = "画中画完成";
                AppendLog($"画中画完成：{result.OutputPath}");
                return;
            }

            if (string.Equals(result.ErrorMessage, "已取消", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(result.ErrorMessage, "Cancelled", StringComparison.OrdinalIgnoreCase))
            {
                ClipStatusMessage = "画中画已取消";
                StatusMessage = "画中画已取消";
                AppendLog("画中画已取消。");
                return;
            }

            ClipStatusMessage = $"画中画失败：{result.ErrorMessage}";
            StatusMessage = "画中画失败";
            AppendLog($"画中画失败：{result.ErrorMessage}");
        }
        finally
        {
            IsClipRunning = false;
            _clipCancellationTokenSource?.Dispose();
            _clipCancellationTokenSource = null;
        }
    }

    private async Task StartSpeedChangeAsync()
    {
        if (!CanStartSpeedChange())
        {
            return;
        }

        if (!TryParseOptionalTimeSpan(ClipStartTimeText, out var startTime) || startTime is null)
        {
            ClipStatusMessage = "开始时间格式无效，请使用 hh:mm:ss 或秒数";
            StatusMessage = "变速参数无效";
            return;
        }

        if (!TryParseOptionalTimeSpan(ClipDurationText, out var duration) || duration is null)
        {
            ClipStatusMessage = "截取时长格式无效，请使用 hh:mm:ss 或秒数";
            StatusMessage = "变速参数无效";
            return;
        }

        if (!TryParsePositiveDouble(ClipSpeedFactorText, out var speedFactor) || speedFactor < 0.5 || speedFactor > 2.0)
        {
            ClipStatusMessage = "变速倍率必须介于 0.5 到 2.0";
            StatusMessage = "变速参数无效";
            return;
        }

        if (startTime.Value < TimeSpan.Zero || duration.Value <= TimeSpan.Zero)
        {
            ClipStatusMessage = "开始时间和截取时长必须有效";
            StatusMessage = "变速参数无效";
            return;
        }

        if (_clipSourceDuration > TimeSpan.Zero && startTime.Value + duration.Value > _clipSourceDuration)
        {
            ClipStatusMessage = "变速区间超出媒体总时长";
            StatusMessage = "变速参数无效";
            return;
        }

        RefreshSpeedOutputPathPreview();
        ClipProgress = 0;
        ClipSpeed = string.Empty;
        IsClipRunning = true;
        _clipCancellationTokenSource = new CancellationTokenSource();
        var outputPath = SpeedOutputPathPreview;
        var encoder = _hardwareDetectionService.ResolveVideoEncoder(Settings.VideoEncoderMode, _isNvencAvailable);

        ClipStatusMessage = $"正在生成 {speedFactor:0.###}x 变速片段";
        StatusMessage = "正在执行视频变速";
        AppendLog($"开始视频变速：{ClipInputPath} -> {outputPath} | 起点 {FormatTimeSpan(startTime.Value)} | 时长 {FormatTimeSpan(duration.Value)} | 倍率 {speedFactor:0.###}x");

        try
        {
            var result = await _videoClipService.ChangeSpeedAsync(
                ClipInputPath,
                outputPath,
                startTime.Value,
                duration.Value,
                speedFactor,
                _clipHasAudio,
                encoder,
                Settings.NvencPreset,
                Settings.Cq,
                Settings.AudioBitrateKbps,
                (progress, speed) =>
                {
                    _ = System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
                    {
                        ClipProgress = Math.Round(progress, 2);
                        if (!string.IsNullOrWhiteSpace(speed) && !string.Equals(speed, "done", StringComparison.OrdinalIgnoreCase))
                        {
                            ClipSpeed = speed;
                        }
                    });
                },
                _clipCancellationTokenSource.Token);

            if (result.Success)
            {
                ClipProgress = 100;
                ClipSpeed = "done";
                ClipStatusMessage = $"变速完成：{Path.GetFileName(result.OutputPath)}";
                StatusMessage = "视频变速完成";
                AppendLog($"视频变速完成：{result.OutputPath}");
                return;
            }

            if (string.Equals(result.ErrorMessage, "已取消", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(result.ErrorMessage, "Cancelled", StringComparison.OrdinalIgnoreCase))
            {
                ClipStatusMessage = "视频变速已取消";
                StatusMessage = "视频变速已取消";
                AppendLog("视频变速已取消。");
                return;
            }

            ClipStatusMessage = $"变速失败：{result.ErrorMessage}";
            StatusMessage = "视频变速失败";
            AppendLog($"视频变速失败：{result.ErrorMessage}");
        }
        finally
        {
            IsClipRunning = false;
            _clipCancellationTokenSource?.Dispose();
            _clipCancellationTokenSource = null;
        }
    }

    private async Task StartReverseAsync()
    {
        if (!CanStartFastClip())
        {
            return;
        }

        if (!TryParseOptionalTimeSpan(ClipStartTimeText, out var startTime) || startTime is null)
        {
            ClipStatusMessage = "开始时间格式无效，请使用 hh:mm:ss 或秒数";
            StatusMessage = "倒放参数无效";
            return;
        }

        if (!TryParseOptionalTimeSpan(ClipDurationText, out var duration) || duration is null)
        {
            ClipStatusMessage = "截取时长格式无效，请使用 hh:mm:ss 或秒数";
            StatusMessage = "倒放参数无效";
            return;
        }

        if (startTime.Value < TimeSpan.Zero || duration.Value <= TimeSpan.Zero)
        {
            ClipStatusMessage = "开始时间和截取时长必须有效";
            StatusMessage = "倒放参数无效";
            return;
        }

        if (_clipSourceDuration > TimeSpan.Zero && startTime.Value + duration.Value > _clipSourceDuration)
        {
            ClipStatusMessage = "倒放区间超出媒体总时长";
            StatusMessage = "倒放参数无效";
            return;
        }

        RefreshReverseOutputPathPreview();
        ClipProgress = 0;
        ClipSpeed = string.Empty;
        IsClipRunning = true;
        _clipCancellationTokenSource = new CancellationTokenSource();
        var outputPath = ReverseOutputPathPreview;
        var encoder = _hardwareDetectionService.ResolveVideoEncoder(Settings.VideoEncoderMode, _isNvencAvailable);

        ClipStatusMessage = "正在生成倒放片段";
        StatusMessage = "正在执行视频倒放";
        AppendLog($"开始视频倒放：{ClipInputPath} -> {outputPath} | 起点 {FormatTimeSpan(startTime.Value)} | 时长 {FormatTimeSpan(duration.Value)}");

        try
        {
            var result = await _videoClipService.ReverseAsync(
                ClipInputPath,
                outputPath,
                startTime.Value,
                duration.Value,
                _clipHasAudio,
                encoder,
                Settings.NvencPreset,
                Settings.Cq,
                Settings.AudioBitrateKbps,
                (progress, speed) =>
                {
                    _ = System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
                    {
                        ClipProgress = Math.Round(progress, 2);
                        if (!string.IsNullOrWhiteSpace(speed) && !string.Equals(speed, "done", StringComparison.OrdinalIgnoreCase))
                        {
                            ClipSpeed = speed;
                        }
                    });
                },
                _clipCancellationTokenSource.Token);

            if (result.Success)
            {
                ClipProgress = 100;
                ClipSpeed = "done";
                ClipStatusMessage = $"倒放完成：{Path.GetFileName(result.OutputPath)}";
                StatusMessage = "视频倒放完成";
                AppendLog($"视频倒放完成：{result.OutputPath}");
                return;
            }

            if (string.Equals(result.ErrorMessage, "已取消", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(result.ErrorMessage, "Cancelled", StringComparison.OrdinalIgnoreCase))
            {
                ClipStatusMessage = "视频倒放已取消";
                StatusMessage = "视频倒放已取消";
                AppendLog("视频倒放已取消。");
                return;
            }

            ClipStatusMessage = $"倒放失败：{result.ErrorMessage}";
            StatusMessage = "视频倒放失败";
            AppendLog($"视频倒放失败：{result.ErrorMessage}");
        }
        finally
        {
            IsClipRunning = false;
            _clipCancellationTokenSource?.Dispose();
            _clipCancellationTokenSource = null;
        }
    }

    private async Task StartVerticalAdaptAsync()
    {
        if (!CanStartVerticalAdapt())
        {
            return;
        }

        if (_clipSourceDuration <= TimeSpan.Zero)
        {
            ClipStatusMessage = "媒体时长未知，无法执行竖屏适配";
            StatusMessage = "竖屏适配参数无效";
            return;
        }

        RefreshVerticalOutputPathPreview();
        ClipProgress = 0;
        ClipSpeed = string.Empty;
        IsClipRunning = true;
        _clipCancellationTokenSource = new CancellationTokenSource();
        var outputPath = VerticalOutputPathPreview;
        var encoder = _hardwareDetectionService.ResolveVideoEncoder(Settings.VideoEncoderMode, _isNvencAvailable);
        var modeLabel = SelectedVerticalMode == VerticalMode.CropCenter ? "中心裁切" : "模糊背景";

        ClipStatusMessage = $"正在执行竖屏适配：{modeLabel}";
        StatusMessage = "正在执行竖屏适配";
        AppendLog($"开始竖屏适配：{ClipInputPath} -> {outputPath} | 模式 {modeLabel} | 编码器 {encoder}");

        try
        {
            var result = await _videoClipService.ConvertToVerticalAsync(
                ClipInputPath,
                outputPath,
                SelectedVerticalMode,
                encoder,
                Settings.NvencPreset,
                Settings.Cq,
                Settings.AudioBitrateKbps,
                _clipSourceDuration.TotalSeconds,
                (progress, speed) =>
                {
                    _ = System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
                    {
                        ClipProgress = Math.Round(progress, 2);
                        if (!string.IsNullOrWhiteSpace(speed) && !string.Equals(speed, "done", StringComparison.OrdinalIgnoreCase))
                        {
                            ClipSpeed = speed;
                        }
                    });
                },
                _clipCancellationTokenSource.Token);

            if (result.Success)
            {
                ClipProgress = 100;
                ClipSpeed = "done";
                ClipStatusMessage = $"竖屏适配完成：{Path.GetFileName(result.OutputPath)}";
                StatusMessage = "竖屏适配完成";
                AppendLog($"竖屏适配完成：{result.OutputPath}");
                return;
            }

            if (string.Equals(result.ErrorMessage, "已取消", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(result.ErrorMessage, "Cancelled", StringComparison.OrdinalIgnoreCase))
            {
                ClipStatusMessage = "竖屏适配已取消";
                StatusMessage = "竖屏适配已取消";
                AppendLog("竖屏适配已取消。");
                return;
            }

            ClipStatusMessage = $"竖屏适配失败：{result.ErrorMessage}";
            StatusMessage = "竖屏适配失败";
            AppendLog($"竖屏适配失败：{result.ErrorMessage}");
        }
        finally
        {
            IsClipRunning = false;
            _clipCancellationTokenSource?.Dispose();
            _clipCancellationTokenSource = null;
        }
    }

    private void ChooseDouyinBgm()
    {
        var path = _userDialogService.PickMediaFile(Settings.InputDirectory);
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        DouyinBgmPath = path;
        if (!_clipHasAudio)
        {
            DouyinStatusMessage = "已选择 BGM，可开始抖音直出";
        }
        else
        {
            DouyinStatusMessage = $"已选择 BGM：{Path.GetFileName(path)}";
        }
    }

    private void ClearDouyinBgm()
    {
        DouyinBgmPath = string.Empty;
        DouyinStatusMessage = _clipHasAudio
            ? "已清空 BGM，将仅使用原始音轨"
            : "已清空 BGM，当前源文件无音轨";
    }

    private async Task StartDouyinExportAsync()
    {
        if (!CanStartDouyinExport())
        {
            return;
        }

        if (!TryParseUnitInterval(DouyinSourceVolumeText, out var sourceVolume))
        {
            DouyinStatusMessage = "原声音量格式无效，请填写 0 到 1 之间的小数";
            StatusMessage = "抖音直出参数无效";
            return;
        }

        if (!TryParseUnitInterval(DouyinBgmVolumeText, out var bgmVolume))
        {
            DouyinStatusMessage = "BGM 音量格式无效，请填写 0 到 1 之间的小数";
            StatusMessage = "抖音直出参数无效";
            return;
        }

        if (_clipSourceDuration <= TimeSpan.Zero)
        {
            DouyinStatusMessage = "媒体时长未知，无法执行抖音直出";
            StatusMessage = "抖音直出参数无效";
            return;
        }

        RefreshDouyinOutputPathPreview();
        DouyinProgress = 0;
        DouyinSpeed = string.Empty;
        IsDouyinExporting = true;
        _douyinExportCancellationTokenSource = new CancellationTokenSource();
        var outputPath = DouyinOutputPathPreview;
        var encoder = _hardwareDetectionService.ResolveVideoEncoder(Settings.VideoEncoderMode, _isNvencAvailable);

        DouyinStatusMessage = "正在执行抖音直出";
        StatusMessage = "正在执行抖音直出";
        AppendLog($"开始抖音直出：{ClipInputPath} -> {outputPath} | 模板 {SelectedDouyinTemplatePreset} | BGM {(string.IsNullOrWhiteSpace(DouyinBgmPath) ? "无" : Path.GetFileName(DouyinBgmPath))}");

        try
        {
            var subtitleOrdinal = DouyinBurnSubtitles ? _douyinSubtitleStreamOrdinal : null;
            var result = await _douyinExportService.ExportAsync(
                ClipInputPath,
                outputPath,
                DouyinBgmPath,
                SelectedDouyinTemplatePreset,
                subtitleOrdinal,
                DouyinTitleText,
                DouyinWatermarkText,
                sourceVolume,
                bgmVolume,
                _clipHasAudio,
                _clipSourceDuration.TotalSeconds,
                encoder,
                Settings.NvencPreset,
                Settings.Cq,
                Settings.AudioBitrateKbps,
                (progress, speed) =>
                {
                    _ = System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
                    {
                        DouyinProgress = Math.Round(progress, 2);
                        if (!string.IsNullOrWhiteSpace(speed) && !string.Equals(speed, "done", StringComparison.OrdinalIgnoreCase))
                        {
                            DouyinSpeed = speed;
                        }
                    });
                },
                _douyinExportCancellationTokenSource.Token);

            if (result.Success)
            {
                DouyinProgress = 100;
                DouyinSpeed = "done";
                DouyinStatusMessage = $"抖音直出完成：{Path.GetFileName(result.OutputPath)}";
                StatusMessage = "抖音直出完成";
                AppendLog($"抖音直出完成：{result.OutputPath}");
                return;
            }

            if (string.Equals(result.ErrorMessage, "已取消", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(result.ErrorMessage, "Cancelled", StringComparison.OrdinalIgnoreCase))
            {
                DouyinStatusMessage = "抖音直出已取消";
                StatusMessage = "抖音直出已取消";
                AppendLog("抖音直出已取消。");
                return;
            }

            DouyinStatusMessage = $"抖音直出失败：{result.ErrorMessage}";
            StatusMessage = "抖音直出失败";
            AppendLog($"抖音直出失败：{result.ErrorMessage}");
        }
        finally
        {
            IsDouyinExporting = false;
            _douyinExportCancellationTokenSource?.Dispose();
            _douyinExportCancellationTokenSource = null;
        }
    }

    private async Task StartBatchDouyinExportAsync()
    {
        if (!CanStartBatchDouyinExport())
        {
            return;
        }

        if (!TryParseUnitInterval(DouyinSourceVolumeText, out var sourceVolume))
        {
            DouyinStatusMessage = "原声音量格式无效，请填写 0 到 1 之间的小数";
            StatusMessage = "批量抖音直出参数无效";
            return;
        }

        if (!TryParseUnitInterval(DouyinBgmVolumeText, out var bgmVolume))
        {
            DouyinStatusMessage = "BGM 音量格式无效，请填写 0 到 1 之间的小数";
            StatusMessage = "批量抖音直出参数无效";
            return;
        }

        var encoder = _hardwareDetectionService.ResolveVideoEncoder(Settings.VideoEncoderMode, _isNvencAvailable);
        var jobsToProcess = Jobs
            .Where(job => File.Exists(job.InputPath))
            .ToList();

        IsDouyinExporting = true;
        _douyinExportCancellationTokenSource = new CancellationTokenSource();
        DouyinProgress = 0;
        DouyinSpeed = string.Empty;
        StatusMessage = "正在批量执行抖音直出";
        DouyinStatusMessage = $"正在准备批量直出，共 {jobsToProcess.Count} 个文件";

        try
        {
            var successCount = 0;
            var failedCount = 0;

            for (var index = 0; index < jobsToProcess.Count; index++)
            {
                var job = jobsToProcess[index];
                var cancellationToken = _douyinExportCancellationTokenSource.Token;
                cancellationToken.ThrowIfCancellationRequested();

                DouyinStatusMessage = $"正在处理 {index + 1}/{jobsToProcess.Count}：{job.FileName}";
                AppendLog($"开始批量抖音直出：{job.InputPath}");

                MediaProbeResult? probe;
                try
                {
                    probe = await _ffprobeService.ProbeAsync(job.InputPath, cancellationToken);
                }
                catch (Exception ex)
                {
                    failedCount++;
                    AppendLog($"批量抖音直出跳过 {job.FileName}：媒体分析失败 | {ex.Message}");
                    continue;
                }

                if (probe is null || probe.Duration <= TimeSpan.Zero)
                {
                    failedCount++;
                    AppendLog($"批量抖音直出跳过 {job.FileName}：媒体分析结果无效。");
                    continue;
                }

                var hasAudio = probe.AudioTracks.Count > 0;
                if (!hasAudio && (string.IsNullOrWhiteSpace(DouyinBgmPath) || !File.Exists(DouyinBgmPath)))
                {
                    failedCount++;
                    AppendLog($"批量抖音直出跳过 {job.FileName}：源文件无音轨且未配置 BGM。");
                    continue;
                }

                var subtitleOrdinal = DouyinBurnSubtitles
                    ? await ResolveDouyinSubtitleStreamOrdinalAsync(job.InputPath, probe, cancellationToken)
                    : null;

                var outputPath = ResolveDouyinOutputPath(job.InputPath);
                var result = await _douyinExportService.ExportAsync(
                    job.InputPath,
                    outputPath,
                    DouyinBgmPath,
                    SelectedDouyinTemplatePreset,
                    subtitleOrdinal,
                    DouyinTitleText,
                    DouyinWatermarkText,
                    sourceVolume,
                    bgmVolume,
                    hasAudio,
                    probe.Duration.TotalSeconds,
                    encoder,
                    Settings.NvencPreset,
                    Settings.Cq,
                    Settings.AudioBitrateKbps,
                    (progress, speed) =>
                    {
                        _ = System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
                        {
                            var baseProgress = (double)index / jobsToProcess.Count * 100d;
                            var scaledProgress = progress / jobsToProcess.Count;
                            DouyinProgress = Math.Round(Math.Min(baseProgress + scaledProgress, 100), 2);
                            if (!string.IsNullOrWhiteSpace(speed) && !string.Equals(speed, "done", StringComparison.OrdinalIgnoreCase))
                            {
                                DouyinSpeed = speed;
                            }
                        });
                    },
                    cancellationToken);

                if (result.Success)
                {
                    successCount++;
                    AppendLog($"批量抖音直出完成：{result.OutputPath}");
                }
                else
                {
                    failedCount++;
                    AppendLog($"批量抖音直出失败：{job.FileName} | {result.ErrorMessage}");
                }
            }

            DouyinProgress = 100;
            DouyinSpeed = "done";
            DouyinStatusMessage = $"批量抖音直出完成：成功 {successCount}，失败 {failedCount}";
            StatusMessage = "批量抖音直出完成";
        }
        catch (OperationCanceledException)
        {
            DouyinStatusMessage = "批量抖音直出已取消";
            StatusMessage = "批量抖音直出已取消";
            AppendLog("批量抖音直出已取消。");
        }
        finally
        {
            IsDouyinExporting = false;
            _douyinExportCancellationTokenSource?.Dispose();
            _douyinExportCancellationTokenSource = null;
        }
    }

    private async Task StartConcatAsync()
    {
        if (!CanStartConcat())
        {
            return;
        }

        if (!TryParseConcatSegments(ConcatSegmentsText, out var segments, out var errorMessage))
        {
            ConcatSummary = errorMessage;
            ClipStatusMessage = "片段列表无效";
            StatusMessage = "视频拼接参数无效";
            return;
        }

        RefreshConcatOutputPathPreview();
        ClipProgress = 0;
        ClipSpeed = string.Empty;
        IsClipRunning = true;
        _clipCancellationTokenSource = new CancellationTokenSource();
        var outputPath = ConcatOutputPathPreview;
        var encoder = _hardwareDetectionService.ResolveVideoEncoder(Settings.VideoEncoderMode, _isNvencAvailable);
        var totalDuration = TimeSpan.FromTicks(segments.Sum(segment => segment.Duration.Ticks));

        ClipStatusMessage = $"正在执行片段拼接，共 {segments.Count} 段";
        StatusMessage = "正在执行片段拼接";
        AppendLog($"开始片段拼接：{ClipInputPath} -> {outputPath} | 片段 {segments.Count} 段 | 总时长 {FormatTimeSpan(totalDuration)} | 编码器 {encoder}");

        try
        {
            var result = await _videoClipService.ConcatAsync(
                ClipInputPath,
                outputPath,
                segments,
                _clipHasAudio,
                encoder,
                Settings.NvencPreset,
                Settings.Cq,
                Settings.AudioBitrateKbps,
                totalDuration.TotalSeconds,
                (progress, speed) =>
                {
                    _ = System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
                    {
                        ClipProgress = Math.Round(progress, 2);
                        if (!string.IsNullOrWhiteSpace(speed) && !string.Equals(speed, "done", StringComparison.OrdinalIgnoreCase))
                        {
                            ClipSpeed = speed;
                        }
                    });
                },
                _clipCancellationTokenSource.Token);

            if (result.Success)
            {
                ClipProgress = 100;
                ClipSpeed = "done";
                ClipStatusMessage = $"片段拼接完成：{Path.GetFileName(result.OutputPath)}";
                StatusMessage = "片段拼接完成";
                AppendLog($"片段拼接完成：{result.OutputPath}");
                return;
            }

            if (string.Equals(result.ErrorMessage, "已取消", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(result.ErrorMessage, "Cancelled", StringComparison.OrdinalIgnoreCase))
            {
                ClipStatusMessage = "片段拼接已取消";
                StatusMessage = "片段拼接已取消";
                AppendLog("片段拼接已取消。");
                return;
            }

            ClipStatusMessage = $"片段拼接失败：{result.ErrorMessage}";
            StatusMessage = "片段拼接失败";
            AppendLog($"片段拼接失败：{result.ErrorMessage}");
        }
        finally
        {
            IsClipRunning = false;
            _clipCancellationTokenSource?.Dispose();
            _clipCancellationTokenSource = null;
        }
    }

    private async Task DetectScenesAsync()
    {
        if (!CanDetectScenes())
        {
            return;
        }

        if (!double.TryParse(SceneDetectionThresholdText, NumberStyles.Float, CultureInfo.InvariantCulture, out var threshold) &&
            !double.TryParse(SceneDetectionThresholdText, NumberStyles.Float, CultureInfo.CurrentCulture, out threshold))
        {
            SceneDetectionSummary = "阈值格式无效，请填写 0 到 1 之间的小数";
            ClipStatusMessage = "场景检测参数无效";
            StatusMessage = "场景检测参数无效";
            return;
        }

        if (threshold <= 0 || threshold >= 1)
        {
            SceneDetectionSummary = "阈值必须介于 0 和 1 之间";
            ClipStatusMessage = "场景检测参数无效";
            StatusMessage = "场景检测参数无效";
            return;
        }

        SceneCutPoints.Clear();
        ClipProgress = 0;
        ClipSpeed = string.Empty;
        IsClipRunning = true;
        _clipCancellationTokenSource = new CancellationTokenSource();
        SceneDetectionSummary = $"正在检测场景切点，阈值 {threshold:0.00}";
        ClipStatusMessage = "正在执行场景检测";
        StatusMessage = "正在执行场景检测";
        AppendLog($"开始场景检测：{ClipInputPath} | threshold={threshold:0.00}");

        try
        {
            var cutPoints = await _videoClipService.DetectScenesAsync(
                ClipInputPath,
                threshold,
                _clipCancellationTokenSource.Token);

            foreach (var point in cutPoints)
            {
                SceneCutPoints.Add(point);
            }

            ClipProgress = 100;
            ClipSpeed = "done";
            SceneDetectionSummary = cutPoints.Count == 0
                ? $"未检测到场景切点 | 阈值 {threshold:0.00}"
                : $"已检测到 {cutPoints.Count} 个场景切点 | 阈值 {threshold:0.00}";
            AutoSegmentSummary = cutPoints.Count == 0
                ? "暂无切点，无法自动生成片段"
                : "已检测到切点，可直接生成自动分段并回填到拼接列表";
            ClipStatusMessage = "场景检测完成";
            StatusMessage = "场景检测完成";
            AppendLog(SceneDetectionSummary);
        }
        catch (OperationCanceledException)
        {
            SceneDetectionSummary = "场景检测已取消";
            ClipStatusMessage = "场景检测已取消";
            StatusMessage = "场景检测已取消";
            AppendLog("场景检测已取消。");
        }
        catch (Exception ex)
        {
            SceneDetectionSummary = $"场景检测失败：{ex.Message}";
            ClipStatusMessage = "场景检测失败";
            StatusMessage = "场景检测失败";
            AppendLog($"场景检测失败：{ex.Message}");
        }
        finally
        {
            IsClipRunning = false;
            _clipCancellationTokenSource?.Dispose();
            _clipCancellationTokenSource = null;
        }
    }

    private async Task GenerateCoverCandidatesAsync()
    {
        if (!CanGenerateCoverCandidates())
        {
            return;
        }

        var candidateTimes = SelectCoverCandidateTimes();
        if (candidateTimes.Count == 0)
        {
            CoverCandidatesSummary = "没有可用的场景切点来生成封面候选";
            StatusMessage = "封面候选生成失败";
            return;
        }

        IsClipRunning = true;
        _clipCancellationTokenSource = new CancellationTokenSource();
        ClipProgress = 0;
        ClipSpeed = string.Empty;
        CoverCandidates.Clear();
        var outputDirectory = Path.Combine(ClipOutputDirectoryPath, "cover_candidates", Path.GetFileNameWithoutExtension(ClipInputPath));
        var filePrefix = $"{Path.GetFileNameWithoutExtension(ClipInputPath)}-cover";

        CoverCandidatesSummary = $"正在从 {candidateTimes.Count} 个候选时间点抽帧";
        ClipStatusMessage = "正在生成封面候选";
        StatusMessage = "正在生成封面候选";
        AppendLog($"开始生成封面候选：{ClipInputPath} | 时间点 {string.Join(", ", candidateTimes.Select(time => $"{time:0.000}s"))}");

        try
        {
            var captureResult = await _nativeMediaCoreService.CaptureDiagnosticFramesAsync(
                ClipInputPath,
                outputDirectory,
                filePrefix,
                candidateTimes,
                _clipCancellationTokenSource.Token);

            if (!captureResult.Success)
            {
                CoverCandidatesSummary = $"封面候选抽帧失败：{captureResult.Message}";
                ClipStatusMessage = "封面候选生成失败";
                StatusMessage = "封面候选生成失败";
                AppendLog($"封面候选抽帧失败：{captureResult.Message}");
                return;
            }

            var report = await _frameInspectionService.AnalyzeAsync(
                ClipInputPath,
                captureResult.OutputDirectory,
                captureResult.Source,
                captureResult.Samples,
                _clipCancellationTokenSource.Token);

            var rankedCandidates = report.Samples
                .Where(sample => sample.OutputExists)
                .OrderBy(sample => sample.NeedsAttention)
                .ThenByDescending(sample => sample.ContrastStdDev)
                .ThenBy(sample => Math.Abs(sample.AverageLuma - 128))
                .ToList();

            foreach (var candidate in rankedCandidates)
            {
                CoverCandidates.Add(candidate);
            }

            CoverCandidatesDirectory = captureResult.OutputDirectory;
            CoverCandidatesSummary = rankedCandidates.Count == 0
                ? "已完成抽帧，但没有可用的封面图片"
                : $"已生成 {rankedCandidates.Count} 张封面候选，优先展示对比度更高且曝光更稳的画面";
            ClipProgress = 100;
            ClipSpeed = "done";
            ClipStatusMessage = "封面候选生成完成";
            StatusMessage = "封面候选生成完成";
            AppendLog($"封面候选生成完成：{captureResult.OutputDirectory} | 数量 {rankedCandidates.Count}");
        }
        catch (OperationCanceledException)
        {
            CoverCandidatesSummary = "封面候选生成已取消";
            ClipStatusMessage = "封面候选生成已取消";
            StatusMessage = "封面候选生成已取消";
            AppendLog("封面候选生成已取消。");
        }
        catch (Exception ex)
        {
            CoverCandidatesSummary = $"封面候选生成失败：{ex.Message}";
            ClipStatusMessage = "封面候选生成失败";
            StatusMessage = "封面候选生成失败";
            AppendLog($"封面候选生成失败：{ex.Message}");
        }
        finally
        {
            IsClipRunning = false;
            _clipCancellationTokenSource?.Dispose();
            _clipCancellationTokenSource = null;
        }
    }

    private async Task DetectBlackSegmentsAsync()
    {
        if (!CanDetectScenes())
        {
            return;
        }

        if (!TryParsePositiveDouble(BlackDetectPictureThresholdText, out var pictureThreshold) ||
            pictureThreshold <= 0 || pictureThreshold >= 1)
        {
            BlackDetectSummary = "画面阈值无效，请填写 0 到 1 之间的小数";
            ClipStatusMessage = "黑场检测参数无效";
            StatusMessage = "黑场检测参数无效";
            return;
        }

        if (!TryParsePositiveDouble(BlackDetectPixelThresholdText, out var pixelThreshold) ||
            pixelThreshold <= 0 || pixelThreshold >= 1)
        {
            BlackDetectSummary = "像素阈值无效，请填写 0 到 1 之间的小数";
            ClipStatusMessage = "黑场检测参数无效";
            StatusMessage = "黑场检测参数无效";
            return;
        }

        if (!TryParsePositiveDouble(BlackDetectMinimumDurationText, out var minimumDuration) || minimumDuration <= 0)
        {
            BlackDetectSummary = "最短时长无效，请填写大于 0 的秒数";
            ClipStatusMessage = "黑场检测参数无效";
            StatusMessage = "黑场检测参数无效";
            return;
        }

        BlackSegments.Clear();
        ClipProgress = 0;
        ClipSpeed = string.Empty;
        IsClipRunning = true;
        _clipCancellationTokenSource = new CancellationTokenSource();
        BlackDetectSummary = "正在检测黑场区间";
        ClipStatusMessage = "正在执行黑场检测";
        StatusMessage = "正在执行黑场检测";
        AppendLog($"开始黑场检测：{ClipInputPath} | pic_th={pictureThreshold:0.###} pix_th={pixelThreshold:0.###} d={minimumDuration:0.###}");

        try
        {
            var segments = await _videoClipService.DetectBlackSegmentsAsync(
                ClipInputPath,
                pictureThreshold,
                pixelThreshold,
                minimumDuration,
                _clipCancellationTokenSource.Token);

            foreach (var segment in segments)
            {
                BlackSegments.Add(segment);
            }

            ClipProgress = 100;
            ClipSpeed = "done";
            BlackDetectSummary = segments.Count == 0
                ? "未检测到黑场区间"
                : $"已检测到 {segments.Count} 段黑场区间";
            ClipStatusMessage = "黑场检测完成";
            StatusMessage = "黑场检测完成";
            AppendLog(BlackDetectSummary);
        }
        catch (OperationCanceledException)
        {
            BlackDetectSummary = "黑场检测已取消";
            ClipStatusMessage = "黑场检测已取消";
            StatusMessage = "黑场检测已取消";
            AppendLog("黑场检测已取消。");
        }
        catch (Exception ex)
        {
            BlackDetectSummary = $"黑场检测失败：{ex.Message}";
            ClipStatusMessage = "黑场检测失败";
            StatusMessage = "黑场检测失败";
            AppendLog($"黑场检测失败：{ex.Message}");
        }
        finally
        {
            IsClipRunning = false;
            _clipCancellationTokenSource?.Dispose();
            _clipCancellationTokenSource = null;
        }
    }

    private async Task DetectFreezeSegmentsAsync()
    {
        if (!CanDetectScenes())
        {
            return;
        }

        if (!TryParsePositiveDouble(FreezeDetectNoiseThresholdText, out var noiseThreshold) || noiseThreshold <= 0)
        {
            FreezeDetectSummary = "噪声阈值无效，请填写大于 0 的数值";
            ClipStatusMessage = "冻帧检测参数无效";
            StatusMessage = "冻帧检测参数无效";
            return;
        }

        if (!TryParsePositiveDouble(FreezeDetectMinimumDurationText, out var minimumDuration) || minimumDuration <= 0)
        {
            FreezeDetectSummary = "最短时长无效，请填写大于 0 的秒数";
            ClipStatusMessage = "冻帧检测参数无效";
            StatusMessage = "冻帧检测参数无效";
            return;
        }

        FreezeSegments.Clear();
        ClipProgress = 0;
        ClipSpeed = string.Empty;
        IsClipRunning = true;
        _clipCancellationTokenSource = new CancellationTokenSource();
        FreezeDetectSummary = "正在检测冻帧区间";
        ClipStatusMessage = "正在执行冻帧检测";
        StatusMessage = "正在执行冻帧检测";
        AppendLog($"开始冻帧检测：{ClipInputPath} | noise={noiseThreshold:0.###} d={minimumDuration:0.###}");

        try
        {
            var segments = await _videoClipService.DetectFreezeSegmentsAsync(
                ClipInputPath,
                noiseThreshold,
                minimumDuration,
                _clipCancellationTokenSource.Token);

            foreach (var segment in segments)
            {
                FreezeSegments.Add(segment);
            }

            ClipProgress = 100;
            ClipSpeed = "done";
            FreezeDetectSummary = segments.Count == 0
                ? "未检测到冻帧区间"
                : $"已检测到 {segments.Count} 段冻帧区间";
            ClipStatusMessage = "冻帧检测完成";
            StatusMessage = "冻帧检测完成";
            AppendLog(FreezeDetectSummary);
        }
        catch (OperationCanceledException)
        {
            FreezeDetectSummary = "冻帧检测已取消";
            ClipStatusMessage = "冻帧检测已取消";
            StatusMessage = "冻帧检测已取消";
            AppendLog("冻帧检测已取消。");
        }
        catch (Exception ex)
        {
            FreezeDetectSummary = $"冻帧检测失败：{ex.Message}";
            ClipStatusMessage = "冻帧检测失败";
            StatusMessage = "冻帧检测失败";
            AppendLog($"冻帧检测失败：{ex.Message}");
        }
        finally
        {
            IsClipRunning = false;
            _clipCancellationTokenSource?.Dispose();
            _clipCancellationTokenSource = null;
        }
    }

    private async Task StartQueueLegacyAsync()
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

            foreach (var job in Jobs.Where(job => job.Status is JobStatus.Pending or JobStatus.Failed).ToList())
            {
                var cancellationToken = _runCancellationTokenSource.Token;
                job.OutputPath = BuildOutputPath(job.InputPath);
                job.Speed = string.Empty;
                job.Progress = 0;
                job.Status = JobStatus.Probing;
                job.Message = "正在读取媒体信息";
                job.SubtitleAnalysisSource = string.Empty;
                job.SubtitleKindSummary = string.Empty;
                job.DanmakuSourceSummary = string.Empty;
                job.DanmakuPreparationSummary = string.Empty;
                job.DanmakuXmlPath = string.Empty;
                job.DanmakuAssPath = string.Empty;
                job.DanmakuXmlCommentCount = 0;
                job.DanmakuKeptCommentCount = 0;

                if (!File.Exists(job.InputPath))
                {
                    job.Status = JobStatus.Failed;
                    job.Message = "找不到输入文件";
                    await RecordHistoryAsync(job);
                    RaiseQueueSummaryProperties();
                    continue;
                }

                if (!Settings.OverwriteExisting)
                {
                    var skipValidation = await _outputValidationService.ValidateAsync(job.InputPath, job.OutputPath, cancellationToken: cancellationToken);
                    AppendLog($"输出校验：{skipValidation.Source} | 差值 {skipValidation.DifferenceSeconds:0.000}s | {skipValidation.Message}");
                    if (skipValidation.IsMatch)
                    {
                        job.Status = JobStatus.Skipped;
                        job.Progress = 100;
                        job.Message = "已存在有效输出文件";
                        AppendLog($"已跳过 {job.FileName}：目标文件已存在且校验通过。");
                        await RecordHistoryAsync(job);
                        RaiseQueueSummaryProperties();
                        continue;
                    }
                }

                var storagePreflight = _storagePreflightService.ValidateOutputPath(job.InputPath, job.OutputPath, Settings);
                AppendLog(storagePreflight.Message);
                if (!storagePreflight.HasEnoughSpace)
                {
                    job.Status = JobStatus.Failed;
                    job.Message = "输出目录空间不足";
                    await RecordHistoryAsync(job);
                    RaiseQueueSummaryProperties();
                    continue;
                }

                var probe = await _nativeMediaCoreService.ProbeMediaAsync(job.InputPath, cancellationToken)
                    ?? await _ffprobeService.ProbeAsync(job.InputPath, cancellationToken);

                if (probe is null)
                {
                    job.Status = JobStatus.Failed;
                    job.Message = "媒体分析失败";
                    await RecordHistoryAsync(job);
                    RaiseQueueSummaryProperties();
                    continue;
                }

                job.SourceDurationSeconds = probe.Duration.TotalSeconds;
                AppendLog(probe.Message);

                var videoEncoder = _hardwareDetectionService.ResolveVideoEncoder(Settings.VideoEncoderMode, _isNvencAvailable);
                job.EncoderUsed = videoEncoder;
                job.Status = JobStatus.Running;
                job.Message = "正在准备叠加素材";
                var overlay = await PrepareOverlayAssetsAsync(job, probe, cancellationToken);
                if (!overlay.Success)
                {
                    job.Status = JobStatus.Failed;
                    job.Message = overlay.ErrorMessage;
                    AppendLog($"处理失败 {job.FileName}：{overlay.ErrorMessage}");
                    await RecordHistoryAsync(job);
                    RaiseQueueSummaryProperties();
                    continue;
                }

                ApplyOverlayStateToJob(job, overlay);

                var modeSummary = BuildOverlayModeSummary(overlay.SubtitleStreamOrdinal, overlay.DanmakuAssPath);
                job.Message = $"正在烧录{modeSummary}";
                AppendLog(
                    $"开始处理 {job.FileName}，编码器：{videoEncoder}，模式：{modeSummary}，" +
                    $"音频策略：{(Settings.PreferStereoAudio ? "AAC 立体声" : "AAC 多声道")}，faststart：{(Settings.EnableFaststart ? "开启" : "关闭")}。");

                var arguments = _danmakuBurnCommandBuilder.BuildArguments(
                    job.InputPath,
                    job.OutputPath,
                    overlay.DanmakuAssPath,
                    overlay.SubtitleStreamOrdinal,
                    Settings,
                    videoEncoder);

                var result = await _ffmpegRunner.RunAsync(
                    arguments,
                    job.SourceDurationSeconds,
                    (progress, speed) => UpdateProgress(job, progress, speed),
                    AppendLog,
                    cancellationToken);

                if (cancellationToken.IsCancellationRequested)
                {
                    job.Status = JobStatus.Cancelled;
                    job.Message = "任务已取消";
                    queueWasCancelled = true;
                    await RecordHistoryAsync(job);
                    RaiseQueueSummaryProperties();
                    break;
                }

                if (!result.Success)
                {
                    job.Status = JobStatus.Failed;
                    job.Message = result.ErrorMessage;
                    AppendLog($"处理失败 {job.FileName}：{result.ErrorMessage}");
                    await RecordHistoryAsync(job);
                    RaiseQueueSummaryProperties();
                    continue;
                }

                var validation = await _outputValidationService.ValidateAsync(
                    job.InputPath,
                    job.OutputPath,
                    cancellationToken: cancellationToken);
                AppendLog($"输出校验：{validation.Source} | 差值 {validation.DifferenceSeconds:0.000}s | {validation.Message}");

                if (!validation.IsMatch)
                {
                    job.Status = JobStatus.Failed;
                    job.Message = "输出文件校验失败";
                    AppendLog($"处理失败 {job.FileName}：{validation.Message}");
                    await RecordHistoryAsync(job);
                    RaiseQueueSummaryProperties();
                    continue;
                }

                job.Status = JobStatus.Success;
                job.Progress = 100;
                job.Message = "转换完成";
                AppendLog($"已完成 {job.FileName}");
                await RecordHistoryAsync(job);
                RaiseQueueSummaryProperties();

                if (Settings.DeleteSourceAfterSuccess)
                {
                    File.Delete(job.InputPath);
                    AppendLog($"已删除源文件：{job.InputPath}");
                }
            }
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

    private async Task RefreshSelectedPreviewAsync()
    {
        if (SelectedJob is null || !File.Exists(SelectedJob.InputPath))
        {
            return;
        }

        if (!TryParsePreviewTimeSeconds(SelectedJob, out var previewTimeSeconds, out var parseMessage))
        {
            SelectedPreviewSummary = parseMessage;
            StatusMessage = "叠加预览参数无效";
            return;
        }

        SelectedPreviewSummary = "正在生成叠加预览";
        StatusMessage = "正在生成叠加预览";

        var probe = await _nativeMediaCoreService.ProbeMediaAsync(SelectedJob.InputPath, CancellationToken.None)
            ?? await _ffprobeService.ProbeAsync(SelectedJob.InputPath, CancellationToken.None);

        if (probe is null)
        {
            SelectedPreviewSummary = "媒体分析失败，无法生成预览";
            StatusMessage = "叠加预览失败";
            return;
        }

        SelectedJob.SourceDurationSeconds = probe.Duration.TotalSeconds;
        var overlay = await PrepareOverlayAssetsAsync(SelectedJob, probe, CancellationToken.None);
        if (!overlay.Success)
        {
            SelectedPreviewSummary = overlay.ErrorMessage;
            StatusMessage = "叠加预览失败";
            return;
        }

        ApplyOverlayStateToJob(SelectedJob, overlay);
        await RefreshSelectedDanmakuAnalysisAsync(SelectedJob, overlay);

        var preview = await _overlayFramePreviewService.GenerateAsync(
            SelectedJob.InputPath,
            previewTimeSeconds,
            overlay.SubtitleStreamOrdinal,
            overlay.DanmakuAssPath,
            CancellationToken.None);

        if (!preview.Success)
        {
            SelectedPreviewSummary = $"预览生成失败：{preview.Message}";
            StatusMessage = "叠加预览失败";
            AppendLog($"叠加预览失败：{preview.Message}");
            return;
        }

        SelectedPreviewImagePath = preview.OutputPath;
        SelectedPreviewSummary = $"预览时间 {previewTimeSeconds:0.###}s | {BuildOverlayModeSummary(overlay.SubtitleStreamOrdinal, overlay.DanmakuAssPath)}";
        StatusMessage = "叠加预览已更新";
        AppendLog($"叠加预览已更新：{preview.OutputPath}");
    }

    private void ApplyOverlayStateToJob(TranscodeJob job, OverlayPreparationState overlay)
    {
        job.SubtitleStreamOrdinal = overlay.SubtitleStreamOrdinal;
        job.SubtitleAnalysisSource = overlay.SubtitleAnalysisSource;
        job.SubtitleKindSummary = overlay.SubtitleKindSummary;
        job.DanmakuSourceSummary = overlay.DanmakuSourceSummary;
        job.DanmakuPreparationSummary = overlay.DanmakuPreparationSummary;
        job.DanmakuXmlPath = overlay.DanmakuXmlPath;
        job.DanmakuAssPath = overlay.DanmakuAssPath;
        job.DanmakuXmlCommentCount = overlay.DanmakuXmlCommentCount;
        job.DanmakuKeptCommentCount = overlay.DanmakuKeptCommentCount;
    }

    private async Task RefreshSelectedDanmakuAnalysisAsync(TranscodeJob job, OverlayPreparationState overlay)
    {
        if (!ReferenceEquals(job, SelectedJob))
        {
            return;
        }

        var excludedCommentKeys = ParseExcludedCommentKeys(job);
        if (!string.IsNullOrWhiteSpace(overlay.DanmakuXmlPath) && File.Exists(overlay.DanmakuXmlPath))
        {
            var snapshot = await _danmakuAssGeneratorService.AnalyzeXmlFileAsync(
                overlay.DanmakuXmlPath,
                Settings,
                excludedCommentKeys,
                cancellationToken: CancellationToken.None);

            job.DanmakuXmlCommentCount = snapshot.XmlCommentCount;
            job.DanmakuKeptCommentCount = snapshot.KeptCommentCount;
            SelectedDanmakuComments.Clear();
            foreach (var comment in snapshot.Comments)
            {
                SelectedDanmakuComments.Add(comment);
            }
            RebuildEditableDanmakuComments(snapshot.Comments, excludedCommentKeys);

            SelectedDanmakuAnalysisSummary = $"当前过滤后保留 {snapshot.KeptCommentCount} / {snapshot.XmlCommentCount} 条。手动禁用 {SelectedDanmakuDisabledCount} 条。";
        }
        else
        {
            SelectedDanmakuComments.Clear();
            foreach (var existingComment in EditableSelectedDanmakuComments)
            {
                existingComment.PropertyChanged -= EditableDanmakuCommentOnPropertyChanged;
            }
            EditableSelectedDanmakuComments.Clear();
            SelectedDanmakuAnalysisSummary = string.IsNullOrWhiteSpace(overlay.DanmakuAssPath)
                ? "当前任务未启用弹幕。"
                : "当前弹幕来源为 ASS 直通，暂不支持逐条过滤分析。";
        }

        RaiseSelectedJobProperties();
        RaisePropertyChanged(nameof(HasSelectedDanmakuComments));
        RaisePropertyChanged(nameof(HasEditableSelectedDanmakuComments));
        RaisePropertyChanged(nameof(SelectedDanmakuDisabledCount));
        RaisePropertyChanged(nameof(FilteredDanmakuCountSummary));
        RaisePropertyChanged(nameof(SelectedDanmakuAnalysisSummary));
    }

    private void LoadSelectedDanmakuCommentsFromJob(TranscodeJob? job)
    {
        SelectedDanmakuComments.Clear();
        foreach (var existingComment in EditableSelectedDanmakuComments)
        {
            existingComment.PropertyChanged -= EditableDanmakuCommentOnPropertyChanged;
        }
        EditableSelectedDanmakuComments.Clear();
        if (job is null)
        {
            RaisePropertyChanged(nameof(HasSelectedDanmakuComments));
            RaisePropertyChanged(nameof(HasEditableSelectedDanmakuComments));
            RaisePropertyChanged(nameof(SelectedDanmakuDisabledCount));
            RaisePropertyChanged(nameof(FilteredDanmakuCountSummary));
            return;
        }

        RaisePropertyChanged(nameof(HasSelectedDanmakuComments));
        RaisePropertyChanged(nameof(HasEditableSelectedDanmakuComments));
        RaisePropertyChanged(nameof(SelectedDanmakuDisabledCount));
        RaisePropertyChanged(nameof(FilteredDanmakuCountSummary));
    }

    private void RebuildEditableDanmakuComments(IEnumerable<DanmakuComment> comments, IReadOnlySet<string> excludedCommentKeys)
    {
        foreach (var existingComment in EditableSelectedDanmakuComments)
        {
            existingComment.PropertyChanged -= EditableDanmakuCommentOnPropertyChanged;
        }

        EditableSelectedDanmakuComments.Clear();
        foreach (var comment in comments)
        {
            var editableComment = new EditableDanmakuComment
            {
                Key = comment.Key,
                TimeSeconds = comment.TimeSeconds,
                Mode = comment.Mode,
                Content = comment.Content,
                IsEnabled = !excludedCommentKeys.Contains(comment.Key)
            };
            editableComment.PropertyChanged += EditableDanmakuCommentOnPropertyChanged;
            EditableSelectedDanmakuComments.Add(editableComment);
        }
    }

    private void EditableDanmakuCommentOnPropertyChanged(object? sender, System.ComponentModel.PropertyChangedEventArgs e)
    {
        if (_suppressDanmakuToggleSync ||
            e.PropertyName != nameof(EditableDanmakuComment.IsEnabled) ||
            sender is not EditableDanmakuComment editableComment ||
            SelectedJob is null)
        {
            return;
        }

        var excludedCommentKeys = ParseExcludedCommentKeys(SelectedJob);
        if (editableComment.IsEnabled)
        {
            excludedCommentKeys.Remove(editableComment.Key);
        }
        else
        {
            excludedCommentKeys.Add(editableComment.Key);
        }

        SelectedJob.DanmakuExcludedCommentKeys = string.Join(Environment.NewLine, excludedCommentKeys.OrderBy(key => key, StringComparer.Ordinal));
        SelectedPreviewImagePath = string.Empty;
        SelectedPreviewSummary = "手动禁用列表已更新，请重新分析或刷新预览";
        SelectedDanmakuAnalysisSummary = $"当前样例里已手动禁用 {SelectedDanmakuDisabledCount} 条，重新分析后会更新最终统计。";
        RaisePropertyChanged(nameof(SelectedDanmakuDisabledCount));
        RaisePropertyChanged(nameof(FilteredDanmakuCountSummary));
        NotifyCommandStateChanged();
    }

    private bool FilterEditableDanmakuComment(object item)
    {
        if (item is not EditableDanmakuComment comment)
        {
            return false;
        }

        if (!string.IsNullOrWhiteSpace(DanmakuSearchText) &&
            !comment.Content.Contains(DanmakuSearchText, StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        return SelectedDanmakuModeFilter switch
        {
            "scroll" => comment.Mode is 1 or 6,
            "top" => comment.Mode == 5,
            "bottom" => comment.Mode == 4,
            _ => true
        };
    }

    private static HashSet<string> ParseExcludedCommentKeys(TranscodeJob job)
    {
        return job.DanmakuExcludedCommentKeys
            .Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .ToHashSet(StringComparer.Ordinal);
    }

    private static HashSet<string> ParseKeywordBatchInput(string raw)
    {
        return raw
            .Split(['|', '\r', '\n'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(keyword => !string.IsNullOrWhiteSpace(keyword))
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
    }

    private async Task<OverlayPreparationState> PrepareOverlayAssetsAsync(
        TranscodeJob job,
        MediaProbeResult probe,
        CancellationToken cancellationToken)
    {
        int? subtitleStreamOrdinal = null;
        var analysisParts = new List<string>();
        var summaryParts = new List<string>();
        var danmakuSourceSummary = Settings.EnableDanmaku ? "弹幕准备中" : "弹幕已关闭";
        var danmakuPreparationSummary = Settings.EnableDanmaku ? "弹幕准备中" : "弹幕已关闭";
        string danmakuAssPath = string.Empty;
        string danmakuXmlPath = string.Empty;
        var danmakuXmlCommentCount = 0;
        var danmakuKeptCommentCount = 0;

        if (Settings.BurnEmbeddedSubtitles)
        {
            var nativeAnalysis = await _nativeMediaCoreService.AnalyzeSubtitlesAsync(
                job.InputPath,
                probe.SubtitleTracks,
                cancellationToken);

            var subtitleTracks = nativeAnalysis.SubtitleTracks;
            analysisParts.Add(nativeAnalysis.Source);
            AppendLog(nativeAnalysis.Message);

            var subtitleKindSummary = _subtitleSelectionService.BuildSubtitleKindSummary(subtitleTracks);
            subtitleStreamOrdinal = _subtitleSelectionService.SelectSubtitleTrackOrdinal(
                subtitleTracks,
                Settings.SubtitlePreference);

            if (subtitleStreamOrdinal is null)
            {
                if (!Settings.EnableDanmaku)
                {
                    return OverlayPreparationState.Fail("未找到可用字幕轨");
                }

                summaryParts.Add($"{subtitleKindSummary} | 已回退为仅弹幕");
            }
            else
            {
                summaryParts.Add($"内嵌字幕轨 #{subtitleStreamOrdinal.Value} | {subtitleKindSummary}");
            }
        }
        else
        {
            analysisParts.Add("embedded-disabled");
            summaryParts.Add("内嵌字幕已关闭");
        }

        if (Settings.EnableDanmaku)
        {
            var preparation = await _danmakuPreparationService.PrepareAsync(job, Settings, AppendLog, cancellationToken);
            if (!preparation.Success)
            {
                return OverlayPreparationState.Fail($"弹幕{preparation.FailedStage}失败：{preparation.ErrorMessage}");
            }

            danmakuAssPath = preparation.AssPath;
            danmakuXmlPath = preparation.XmlPath;
            danmakuXmlCommentCount = preparation.XmlCommentCount;
            danmakuKeptCommentCount = preparation.AssCommentCount;
            danmakuSourceSummary = BuildDanmakuSourceSummary(preparation);
            danmakuPreparationSummary = preparation.Summary;
            analysisParts.Add(preparation.Source);
            summaryParts.Add(preparation.KindSummary);
        }

        if (subtitleStreamOrdinal is null && string.IsNullOrWhiteSpace(danmakuAssPath))
        {
            return OverlayPreparationState.Fail("当前没有可烧录的字幕或弹幕");
        }

        return OverlayPreparationState.SuccessState(
            subtitleStreamOrdinal,
            danmakuAssPath,
            danmakuXmlPath,
            danmakuXmlCommentCount,
            danmakuKeptCommentCount,
            string.Join(" + ", analysisParts.Where(part => !string.IsNullOrWhiteSpace(part))),
            string.Join(" | ", summaryParts.Where(part => !string.IsNullOrWhiteSpace(part))),
            danmakuSourceSummary,
            danmakuPreparationSummary);
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

    private static string BuildDanmakuSourceSummary(DanmakuPreparationResult preparation)
    {
        return preparation.Source switch
        {
            "local-ass" => "本地 ASS",
            "local-xml" => "本地 XML",
            "bilibili-danmaku" => "Bilibili XML",
            _ => preparation.Source
        };
    }

    private bool TryParsePreviewTimeSeconds(TranscodeJob job, out double previewTimeSeconds, out string errorMessage)
    {
        if (!double.TryParse(SelectedPreviewTimeText, NumberStyles.Float, CultureInfo.InvariantCulture, out previewTimeSeconds) &&
            !double.TryParse(SelectedPreviewTimeText, NumberStyles.Float, CultureInfo.CurrentCulture, out previewTimeSeconds))
        {
            errorMessage = "预览时间无效，请填写秒数";
            return false;
        }

        if (previewTimeSeconds < 0)
        {
            errorMessage = "预览时间不能小于 0";
            return false;
        }

        if (job.SourceDurationSeconds > 0)
        {
            previewTimeSeconds = Math.Min(previewTimeSeconds, Math.Max(job.SourceDurationSeconds - 0.1, 0));
        }

        errorMessage = string.Empty;
        return true;
    }

    private void Cancel()
    {
        _runCancellationTokenSource?.Cancel();
        StatusMessage = "已请求取消当前任务";
    }

    private void CancelAudioExtraction()
    {
        _audioExtractionCancellationTokenSource?.Cancel();
        AudioStatusMessage = "已请求取消音频提取";
        StatusMessage = "已请求取消音频提取";
    }

    private void CancelClip()
    {
        _clipCancellationTokenSource?.Cancel();
        ClipStatusMessage = "已请求取消当前视频任务";
        StatusMessage = "已请求取消当前视频任务";
    }

    private void CancelDouyinExport()
    {
        _douyinExportCancellationTokenSource?.Cancel();
        DouyinStatusMessage = "已请求取消抖音直出";
        StatusMessage = "已请求取消抖音直出";
    }

    private bool CanExtractAudio()
    {
        return !IsRunning
            && !IsAudioExtracting
            && !IsAudioSilenceDetecting
            && !IsClipRunning
            && !IsDouyinExporting
            && !string.IsNullOrWhiteSpace(AudioInputPath)
            && File.Exists(AudioInputPath)
            && AudioTracks.Count > 0
            && SelectedAudioTrack is not null;
    }

    private bool CanStartAudioMix()
    {
        return !IsRunning
            && !IsAudioExtracting
            && !IsAudioSilenceDetecting
            && !IsClipRunning
            && !IsDouyinExporting
            && !string.IsNullOrWhiteSpace(AudioInputPath)
            && File.Exists(AudioInputPath)
            && !string.IsNullOrWhiteSpace(AudioMixBackgroundPath)
            && File.Exists(AudioMixBackgroundPath)
            && AudioTracks.Count > 0
            && SelectedAudioTrack is not null;
    }

    private bool CanDetectSilence()
    {
        return !IsRunning
            && !IsAudioExtracting
            && !IsAudioSilenceDetecting
            && !IsClipRunning
            && !IsDouyinExporting
            && !string.IsNullOrWhiteSpace(AudioInputPath)
            && File.Exists(AudioInputPath)
            && AudioTracks.Count > 0
            && SelectedAudioTrack is not null;
    }

    private bool CanStartFastClip()
    {
        return !IsRunning
            && !IsAudioExtracting
            && !IsAudioSilenceDetecting
            && !IsClipRunning
            && !IsDouyinExporting
            && !string.IsNullOrWhiteSpace(ClipInputPath)
            && File.Exists(ClipInputPath);
    }

    private bool CanStartSpeedChange()
    {
        return CanStartFastClip()
            && _clipSourceDuration > TimeSpan.Zero
            && TryParsePositiveDouble(ClipSpeedFactorText, out var speedFactor)
            && speedFactor >= 0.5
            && speedFactor <= 2.0;
    }

    private bool CanStartPictureInPicture()
    {
        return CanStartFastClip()
            && _clipSourceDuration > TimeSpan.Zero
            && !string.IsNullOrWhiteSpace(PipOverlayPath)
            && File.Exists(PipOverlayPath)
            && TryParseUnitInterval(PipScaleText, out var pipScale)
            && pipScale > 0
            && pipScale < 1;
    }

    private bool CanStartConcat()
    {
        return !IsRunning
            && !IsAudioExtracting
            && !IsAudioSilenceDetecting
            && !IsClipRunning
            && !IsDouyinExporting
            && !string.IsNullOrWhiteSpace(ClipInputPath)
            && File.Exists(ClipInputPath)
            && _hasValidConcatSegments;
    }

    private bool CanDetectScenes()
    {
        return !IsRunning
            && !IsAudioExtracting
            && !IsAudioSilenceDetecting
            && !IsClipRunning
            && !IsDouyinExporting
            && !string.IsNullOrWhiteSpace(ClipInputPath)
            && File.Exists(ClipInputPath);
    }

    private bool CanGenerateAutoSegments()
    {
        return !IsRunning
            && !IsAudioExtracting
            && !IsAudioSilenceDetecting
            && !IsClipRunning
            && !IsDouyinExporting
            && SceneCutPoints.Count > 0
            && _clipSourceDuration > TimeSpan.Zero;
    }

    private bool CanGenerateCoverCandidates()
    {
        return !IsRunning
            && !IsAudioExtracting
            && !IsAudioSilenceDetecting
            && !IsClipRunning
            && !IsDouyinExporting
            && !string.IsNullOrWhiteSpace(ClipInputPath)
            && File.Exists(ClipInputPath)
            && SceneCutPoints.Count > 0;
    }

    private bool CanStartVerticalAdapt()
    {
        return !IsRunning
            && !IsAudioExtracting
            && !IsAudioSilenceDetecting
            && !IsClipRunning
            && !IsDouyinExporting
            && !string.IsNullOrWhiteSpace(ClipInputPath)
            && File.Exists(ClipInputPath)
            && _clipSourceDuration > TimeSpan.Zero;
    }

    private bool CanStartDouyinExport()
    {
        return !IsRunning
            && !IsAudioExtracting
            && !IsAudioSilenceDetecting
            && !IsClipRunning
            && !IsDouyinExporting
            && !string.IsNullOrWhiteSpace(ClipInputPath)
            && File.Exists(ClipInputPath)
            && _clipSourceDuration > TimeSpan.Zero
            && (_clipHasAudio || (!string.IsNullOrWhiteSpace(DouyinBgmPath) && File.Exists(DouyinBgmPath)));
    }

    private bool CanStartBatchDouyinExport()
    {
        return !IsRunning
            && !IsAudioExtracting
            && !IsAudioSilenceDetecting
            && !IsClipRunning
            && !IsDouyinExporting
            && Jobs.Any(job => File.Exists(job.InputPath));
    }

    private void RecalculateOutputPaths()
    {
        foreach (var job in Jobs)
        {
            job.OutputPath = BuildOutputPath(job.InputPath);
        }

        RefreshAudioOutputPathPreview();
        RefreshAudioMixOutputPathPreview();
        RefreshClipOutputPathPreview();
        RefreshConcatOutputPathPreview();
        RefreshVerticalOutputPathPreview();
        RefreshGifOutputPathPreview();
        RefreshPipOutputPathPreview();
        RefreshSpeedOutputPathPreview();
        RefreshReverseOutputPathPreview();
        RefreshDouyinOutputPathPreview();
    }

    private string BuildOutputPath(string inputPath)
    {
        var suffix = Settings.EnableDanmaku ? "-danmaku" : string.Empty;
        return Path.Combine(Settings.OutputDirectory, $"{Path.GetFileNameWithoutExtension(inputPath)}{suffix}.mp4");
    }

    private void RefreshAudioOutputPathPreview()
    {
        AudioOutputPathPreview = string.IsNullOrWhiteSpace(AudioInputPath)
            ? "未生成"
            : ResolveAudioOutputPath(AudioInputPath);
    }

    private void RefreshAudioMixOutputPathPreview()
    {
        AudioMixOutputPathPreview = string.IsNullOrWhiteSpace(AudioInputPath)
            ? "未生成"
            : ResolveAudioMixOutputPath(AudioInputPath);
    }

    private string ResolveAudioOutputPath(string inputPath)
    {
        var basePath = BuildAudioOutputPath(inputPath);
        if (Settings.OverwriteExisting || !File.Exists(basePath))
        {
            return basePath;
        }

        var directory = Path.GetDirectoryName(basePath)!;
        var fileName = Path.GetFileNameWithoutExtension(basePath);
        var extension = Path.GetExtension(basePath);

        for (var index = 2; index < 1000; index++)
        {
            var candidate = Path.Combine(directory, $"{fileName}-{index}{extension}");
            if (!File.Exists(candidate))
            {
                return candidate;
            }
        }

        return Path.Combine(
            directory,
            $"{fileName}-{DateTime.Now:yyyyMMddHHmmss}{extension}");
    }

    private string BuildAudioOutputPath(string inputPath)
    {
        var extension = AudioCommandBuilder.GetDefaultExtension(SelectedAudioFormat, AudioNormalize);
        return Path.Combine(AudioOutputDirectoryPath, $"{Path.GetFileNameWithoutExtension(inputPath)}{extension}");
    }

    private string ResolveAudioMixOutputPath(string inputPath)
    {
        var basePath = Path.Combine(AudioMixOutputDirectoryPath, $"{Path.GetFileNameWithoutExtension(inputPath)}-mix.m4a");
        return ResolveUniqueOutputPath(basePath);
    }

    private void RefreshClipOutputPathPreview()
    {
        ClipOutputPathPreview = string.IsNullOrWhiteSpace(ClipInputPath)
            ? "未生成"
            : ResolveClipOutputPath(ClipInputPath);
    }

    private string ResolveClipOutputPath(string inputPath)
    {
        var basePath = Path.Combine(ClipOutputDirectoryPath, $"{Path.GetFileNameWithoutExtension(inputPath)}-clip{Path.GetExtension(inputPath)}");
        return ResolveUniqueOutputPath(basePath);
    }

    private void RefreshConcatOutputPathPreview()
    {
        ConcatOutputPathPreview = string.IsNullOrWhiteSpace(ClipInputPath)
            ? "未生成"
            : ResolveConcatOutputPath(ClipInputPath);
    }

    private string ResolveConcatOutputPath(string inputPath)
    {
        var basePath = Path.Combine(ConcatOutputDirectoryPath, $"{Path.GetFileNameWithoutExtension(inputPath)}-concat{Path.GetExtension(inputPath)}");
        return ResolveUniqueOutputPath(basePath);
    }

    private string ResolveUniqueOutputPath(string basePath)
    {
        if (Settings.OverwriteExisting || !File.Exists(basePath))
        {
            return basePath;
        }

        var directory = Path.GetDirectoryName(basePath)!;
        var fileName = Path.GetFileNameWithoutExtension(basePath);
        var extension = Path.GetExtension(basePath);

        for (var index = 2; index < 1000; index++)
        {
            var candidate = Path.Combine(directory, $"{fileName}-{index}{extension}");
            if (!File.Exists(candidate))
            {
                return candidate;
            }
        }

        return Path.Combine(directory, $"{fileName}-{DateTime.Now:yyyyMMddHHmmss}{extension}");
    }

    private void RefreshVerticalOutputPathPreview()
    {
        VerticalOutputPathPreview = string.IsNullOrWhiteSpace(ClipInputPath)
            ? "未生成"
            : ResolveVerticalOutputPath(ClipInputPath);
    }

    private string ResolveVerticalOutputPath(string inputPath)
    {
        var modeSuffix = SelectedVerticalMode == VerticalMode.CropCenter ? "crop9x16" : "blur9x16";
        var basePath = Path.Combine(VerticalOutputDirectoryPath, $"{Path.GetFileNameWithoutExtension(inputPath)}-{modeSuffix}.mp4");
        return ResolveUniqueOutputPath(basePath);
    }

    private void RefreshGifOutputPathPreview()
    {
        GifOutputPathPreview = string.IsNullOrWhiteSpace(ClipInputPath)
            ? "未生成"
            : ResolveGifOutputPath(ClipInputPath);
    }

    private string ResolveGifOutputPath(string inputPath)
    {
        var basePath = Path.Combine(GifOutputDirectoryPath, $"{Path.GetFileNameWithoutExtension(inputPath)}-preview.gif");
        return ResolveUniqueOutputPath(basePath);
    }

    private void RefreshPipOutputPathPreview()
    {
        PipOutputPathPreview = string.IsNullOrWhiteSpace(ClipInputPath)
            ? "未生成"
            : ResolvePipOutputPath(ClipInputPath);
    }

    private string ResolvePipOutputPath(string inputPath)
    {
        var cornerSuffix = SelectedPipCorner switch
        {
            PipCorner.TopLeft => "pip-tl",
            PipCorner.TopRight => "pip-tr",
            PipCorner.BottomLeft => "pip-bl",
            _ => "pip-br"
        };
        var basePath = Path.Combine(PipOutputDirectoryPath, $"{Path.GetFileNameWithoutExtension(inputPath)}-{cornerSuffix}.mp4");
        return ResolveUniqueOutputPath(basePath);
    }

    private void RefreshSpeedOutputPathPreview()
    {
        SpeedOutputPathPreview = string.IsNullOrWhiteSpace(ClipInputPath)
            ? "未生成"
            : ResolveSpeedOutputPath(ClipInputPath);
    }

    private string ResolveSpeedOutputPath(string inputPath)
    {
        var basePath = Path.Combine(VideoFxOutputDirectoryPath, $"{Path.GetFileNameWithoutExtension(inputPath)}-speed{BuildSpeedFactorFileSuffix()}.mp4");
        return ResolveUniqueOutputPath(basePath);
    }

    private void RefreshReverseOutputPathPreview()
    {
        ReverseOutputPathPreview = string.IsNullOrWhiteSpace(ClipInputPath)
            ? "未生成"
            : ResolveReverseOutputPath(ClipInputPath);
    }

    private string ResolveReverseOutputPath(string inputPath)
    {
        var basePath = Path.Combine(VideoFxOutputDirectoryPath, $"{Path.GetFileNameWithoutExtension(inputPath)}-reverse.mp4");
        return ResolveUniqueOutputPath(basePath);
    }

    private void RefreshDouyinOutputPathPreview()
    {
        DouyinOutputPathPreview = string.IsNullOrWhiteSpace(ClipInputPath)
            ? "未生成"
            : ResolveDouyinOutputPath(ClipInputPath);
    }

    private string ResolveDouyinOutputPath(string inputPath)
    {
        var suffix = SelectedDouyinTemplatePreset switch
        {
            DouyinTemplatePreset.CropTitleWatermark => "douyin-crop",
            DouyinTemplatePreset.BlurBgmBoost => "douyin-bgm",
            _ => "douyin-blur"
        };

        var basePath = Path.Combine(DouyinOutputDirectoryPath, $"{Path.GetFileNameWithoutExtension(inputPath)}-{suffix}.mp4");
        return ResolveUniqueOutputPath(basePath);
    }

    private string BuildSpeedFactorFileSuffix()
    {
        if (!TryParsePositiveDouble(ClipSpeedFactorText, out var speedFactor))
        {
            return string.Empty;
        }

        return Math.Round(speedFactor * 100, MidpointRounding.AwayFromZero)
            .ToString("0", CultureInfo.InvariantCulture);
    }

    private void RefreshConcatSegmentsPreview()
    {
        ConcatSegments.Clear();

        if (string.IsNullOrWhiteSpace(ConcatSegmentsText))
        {
            _hasValidConcatSegments = false;
            ConcatSummary = "每行一个片段，格式：开始时间,时长";
            return;
        }

        if (!TryParseConcatSegments(ConcatSegmentsText, out var segments, out var errorMessage))
        {
            _hasValidConcatSegments = false;
            ConcatSummary = errorMessage;
            return;
        }

        foreach (var segment in segments)
        {
            ConcatSegments.Add(segment);
        }

        _hasValidConcatSegments = segments.Count > 0;
        var totalDuration = TimeSpan.FromTicks(segments.Sum(segment => segment.Duration.Ticks));
        var audioSummary = _clipHasAudio ? "沿用主音轨" : "源文件无音轨，仅输出视频";
        ConcatSummary = $"已解析 {segments.Count} 段 | 总时长 {FormatTimeSpan(totalDuration)} | {audioSummary}";
    }

    private bool TryParseConcatSegments(string? raw, out List<ClipConcatSegment> segments, out string errorMessage)
    {
        segments = [];
        errorMessage = string.Empty;

        if (string.IsNullOrWhiteSpace(raw))
        {
            errorMessage = "请至少填写一个片段，格式：开始时间,时长";
            return false;
        }

        var lines = raw
            .Replace("，", ",", StringComparison.Ordinal)
            .Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

        for (var index = 0; index < lines.Length; index++)
        {
            var line = lines[index];
            if (line.StartsWith('#'))
            {
                continue;
            }

            var parts = line.Split([',', '|', ';'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            if (parts.Length != 2)
            {
                parts = line.Split([' ', '\t'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            }

            if (parts.Length != 2)
            {
                errorMessage = $"第 {index + 1} 行格式无效，请使用“开始时间,时长”";
                return false;
            }

            if (!TryParseOptionalTimeSpan(parts[0], out var startTime) || startTime is null)
            {
                errorMessage = $"第 {index + 1} 行开始时间无效";
                return false;
            }

            if (!TryParseOptionalTimeSpan(parts[1], out var duration) || duration is null)
            {
                errorMessage = $"第 {index + 1} 行时长无效";
                return false;
            }

            if (startTime.Value < TimeSpan.Zero)
            {
                errorMessage = $"第 {index + 1} 行开始时间不能小于 0";
                return false;
            }

            if (duration.Value <= TimeSpan.Zero)
            {
                errorMessage = $"第 {index + 1} 行时长必须大于 0";
                return false;
            }

            if (_clipSourceDuration > TimeSpan.Zero)
            {
                if (startTime.Value >= _clipSourceDuration)
                {
                    errorMessage = $"第 {index + 1} 行开始时间超出媒体总时长";
                    return false;
                }

                if (startTime.Value + duration.Value > _clipSourceDuration)
                {
                    errorMessage = $"第 {index + 1} 行截取区间超出媒体总时长";
                    return false;
                }
            }

            segments.Add(new ClipConcatSegment
            {
                Sequence = segments.Count + 1,
                Start = startTime.Value,
                Duration = duration.Value
            });
        }

        if (segments.Count == 0)
        {
            errorMessage = "请至少填写一个有效片段";
            return false;
        }

        return true;
    }

    private IReadOnlyList<double> SelectCoverCandidateTimes()
    {
        if (SceneCutPoints.Count == 0)
        {
            return [];
        }

        var usableTimes = SceneCutPoints
            .Select(point => point.TimeSeconds)
            .Where(time => time > 0.01 && (_clipSourceDuration <= TimeSpan.Zero || time < _clipSourceDuration.TotalSeconds - 0.1))
            .Distinct()
            .OrderBy(time => time)
            .ToList();

        if (usableTimes.Count <= 6)
        {
            return usableTimes;
        }

        var selected = new List<double>(6);
        for (var index = 0; index < 6; index++)
        {
            var sourceIndex = (int)Math.Round(index * (usableTimes.Count - 1d) / 5d, MidpointRounding.AwayFromZero);
            selected.Add(usableTimes[sourceIndex]);
        }

        return selected
            .Distinct()
            .OrderBy(time => time)
            .ToList();
    }

    private void GenerateAutoSegmentsFromScenes()
    {
        if (!CanGenerateAutoSegments())
        {
            return;
        }

        if (!TryParsePositiveDouble(AutoSegmentMinimumDurationText, out var minimumDuration))
        {
            AutoSegmentSummary = "最短片段时长格式无效";
            StatusMessage = "自动分段参数无效";
            return;
        }

        if (!TryParsePositiveDouble(AutoSegmentMaximumDurationText, out var maximumDuration))
        {
            AutoSegmentSummary = "最大片段时长格式无效";
            StatusMessage = "自动分段参数无效";
            return;
        }

        if (maximumDuration < minimumDuration)
        {
            AutoSegmentSummary = "最大片段时长不能小于最短片段时长";
            StatusMessage = "自动分段参数无效";
            return;
        }

        var cutTimes = SceneCutPoints
            .Select(point => Math.Round(point.TimeSeconds, 3))
            .Where(time => time > 0 && time < _clipSourceDuration.TotalSeconds)
            .Distinct()
            .OrderBy(time => time)
            .ToList();

        var boundaries = new List<double> { 0d };
        boundaries.AddRange(cutTimes);
        boundaries.Add(_clipSourceDuration.TotalSeconds);

        var generatedSegments = new List<ClipConcatSegment>();
        for (var index = 0; index < boundaries.Count - 1; index++)
        {
            var start = boundaries[index];
            var end = boundaries[index + 1];
            var duration = end - start;

            if (duration < minimumDuration)
            {
                continue;
            }

            var currentStart = start;
            while (duration > maximumDuration)
            {
                generatedSegments.Add(new ClipConcatSegment
                {
                    Sequence = generatedSegments.Count + 1,
                    Start = TimeSpan.FromSeconds(currentStart),
                    Duration = TimeSpan.FromSeconds(maximumDuration)
                });

                currentStart += maximumDuration;
                duration = end - currentStart;
            }

            if (duration >= minimumDuration)
            {
                generatedSegments.Add(new ClipConcatSegment
                {
                    Sequence = generatedSegments.Count + 1,
                    Start = TimeSpan.FromSeconds(currentStart),
                    Duration = TimeSpan.FromSeconds(duration)
                });
            }
        }

        if (generatedSegments.Count == 0)
        {
            AutoSegmentSummary = "当前切点在给定时长约束下没有生成可用片段";
            StatusMessage = "自动分段未生成结果";
            return;
        }

        ConcatSegmentsText = string.Join(
            Environment.NewLine,
            generatedSegments.Select(segment => $"{segment.StartText},{segment.DurationText}"));

        var totalDuration = TimeSpan.FromTicks(generatedSegments.Sum(segment => segment.Duration.Ticks));
        AutoSegmentSummary = $"已生成 {generatedSegments.Count} 段自动片段，总时长 {FormatTimeSpan(totalDuration)}，已回填到拼接列表";
        StatusMessage = "自动分段已生成";
        AppendLog($"自动分段完成：{generatedSegments.Count} 段 | 总时长 {FormatTimeSpan(totalDuration)} | 最短 {minimumDuration:0.##}s | 最长 {maximumDuration:0.##}s");
        NotifyCommandStateChanged();
    }

    private IEnumerable<string> ExpandIncomingPaths(IEnumerable<string> incomingPaths)
    {
        foreach (var path in incomingPaths)
        {
            if (File.Exists(path))
            {
                yield return path;
                continue;
            }

            if (Directory.Exists(path))
            {
                foreach (var file in Directory.GetFiles(path, "*.mkv", SearchOption.TopDirectoryOnly))
                {
                    yield return file;
                }
            }
        }
    }

    private void OpenAudioOutputDirectory()
    {
        Directory.CreateDirectory(AudioOutputDirectoryPath);
        _userDialogService.OpenFolder(AudioOutputDirectoryPath);
    }

    private void OpenAudioMixOutputDirectory()
    {
        Directory.CreateDirectory(AudioMixOutputDirectoryPath);
        _userDialogService.OpenFolder(AudioMixOutputDirectoryPath);
    }

    private void OpenClipOutputDirectory()
    {
        Directory.CreateDirectory(ClipOutputDirectoryPath);
        _userDialogService.OpenFolder(ClipOutputDirectoryPath);
    }

    private void OpenConcatOutputDirectory()
    {
        Directory.CreateDirectory(ConcatOutputDirectoryPath);
        _userDialogService.OpenFolder(ConcatOutputDirectoryPath);
    }

    private void OpenVerticalOutputDirectory()
    {
        Directory.CreateDirectory(VerticalOutputDirectoryPath);
        _userDialogService.OpenFolder(VerticalOutputDirectoryPath);
    }

    private void OpenDouyinOutputDirectory()
    {
        Directory.CreateDirectory(DouyinOutputDirectoryPath);
        _userDialogService.OpenFolder(DouyinOutputDirectoryPath);
    }

    private void OpenGifOutputDirectory()
    {
        Directory.CreateDirectory(GifOutputDirectoryPath);
        _userDialogService.OpenFolder(GifOutputDirectoryPath);
    }

    private void OpenPipOutputDirectory()
    {
        Directory.CreateDirectory(PipOutputDirectoryPath);
        _userDialogService.OpenFolder(PipOutputDirectoryPath);
    }

    private void OpenVideoFxOutputDirectory()
    {
        Directory.CreateDirectory(VideoFxOutputDirectoryPath);
        _userDialogService.OpenFolder(VideoFxOutputDirectoryPath);
    }

    private void OpenCoverCandidatesDirectory()
    {
        if (Directory.Exists(_coverCandidatesDirectory))
        {
            _userDialogService.OpenFolder(_coverCandidatesDirectory);
        }
    }

    private void UpdateProgress(TranscodeJob job, double progress, string speed)
    {
        _ = System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
        {
            job.Progress = Math.Round(progress, 2);
            if (!string.IsNullOrWhiteSpace(speed) && !string.Equals(speed, "done", StringComparison.OrdinalIgnoreCase))
            {
                job.Speed = speed;
            }
        });
    }

    private void AppendLog(string message)
    {
        var line = $"[{DateTime.Now:HH:mm:ss}] {message}";
        AppFileLogger.Write("MainViewModel", message);
        _ = System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
        {
            LogText = string.IsNullOrWhiteSpace(LogText)
                ? line
                : $"{LogText}{Environment.NewLine}{line}";
        });
    }

    private static string FormatTimeSpan(TimeSpan timeSpan)
    {
        return timeSpan > TimeSpan.Zero ? timeSpan.ToString(@"hh\:mm\:ss\.fff") : "未知";
    }

    private static bool TryParseOptionalTimeSpan(string? raw, out TimeSpan? value)
    {
        value = null;
        if (string.IsNullOrWhiteSpace(raw))
        {
            return true;
        }

        if (TimeSpan.TryParse(raw, CultureInfo.InvariantCulture, out var timeSpan) ||
            TimeSpan.TryParse(raw, CultureInfo.CurrentCulture, out timeSpan))
        {
            value = timeSpan;
            return true;
        }

        if (double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out var seconds) ||
            double.TryParse(raw, NumberStyles.Float, CultureInfo.CurrentCulture, out seconds))
        {
            value = TimeSpan.FromSeconds(seconds);
            return true;
        }

        return false;
    }

    private static bool TryParseUnitInterval(string? raw, out double value)
    {
        value = 0;
        if (string.IsNullOrWhiteSpace(raw))
        {
            return false;
        }

        if (!double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out value) &&
            !double.TryParse(raw, NumberStyles.Float, CultureInfo.CurrentCulture, out value))
        {
            return false;
        }

        return value >= 0 && value <= 1;
    }

    private static bool TryParsePositiveDouble(string? raw, out double value)
    {
        value = 0;
        if (string.IsNullOrWhiteSpace(raw))
        {
            return false;
        }

        if (!double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out value) &&
            !double.TryParse(raw, NumberStyles.Float, CultureInfo.CurrentCulture, out value))
        {
            return false;
        }

        return value > 0;
    }

    private async Task<int?> ResolveDouyinSubtitleStreamOrdinalAsync(
        string inputPath,
        MediaProbeResult probe,
        CancellationToken cancellationToken)
    {
        var nativeAnalysis = await _nativeMediaCoreService.AnalyzeSubtitlesAsync(
            inputPath,
            probe.SubtitleTracks,
            cancellationToken);

        var subtitleTracks = nativeAnalysis.SubtitleTracks;
        var selectedSubtitleOrdinal = _subtitleSelectionService.SelectSubtitleTrackOrdinal(
            subtitleTracks,
            Settings.SubtitlePreference);

        if (selectedSubtitleOrdinal is null ||
            selectedSubtitleOrdinal.Value < 0 ||
            selectedSubtitleOrdinal.Value >= subtitleTracks.Count)
        {
            return null;
        }

        var selectedTrack = subtitleTracks[selectedSubtitleOrdinal.Value];
        return selectedTrack.IsTextBased ? selectedSubtitleOrdinal : null;
    }

    private async Task ExportHistoryAsync(string format)
    {
        var extension = format.ToLowerInvariant();
        var filter = extension == "json"
            ? "JSON 文件 (*.json)|*.json"
            : "文本文件 (*.txt)|*.txt";

        var fileName = $"AnimeTranscoder-任务历史-{DateTime.Now:yyyyMMdd-HHmmss}.{extension}";
        var savePath = _userDialogService.PickSaveFile(
            extension == "json" ? "导出 JSON 历史记录" : "导出文本历史记录",
            filter,
            fileName,
            Settings.OutputDirectory);

        if (string.IsNullOrWhiteSpace(savePath))
        {
            return;
        }

        await _taskHistoryService.ExportAsync(FilteredHistoryEntries, savePath, extension);
        StatusMessage = $"历史记录已导出：{savePath}";
        AppendLog($"已导出历史记录：{savePath}");
    }

    private void ClearHistoryFilters()
    {
        HistoryStatusFilter = "全部";
        HistoryDateFilter = null;
        StatusMessage = "已清空历史筛选条件";
    }

    private async Task RecordHistoryAsync(TranscodeJob job)
    {
        var entry = new TaskHistoryEntry
        {
            InputPath = job.InputPath,
            OutputPath = job.OutputPath,
            FileName = job.FileName,
            Status = job.Status,
            StatusText = job.StatusText,
            Message = job.Message,
            EncoderUsed = job.EncoderUsed,
            SubtitleStreamOrdinal = job.SubtitleStreamOrdinal,
            SubtitleAnalysisSource = string.IsNullOrWhiteSpace(job.SubtitleAnalysisSource) ? "unknown" : job.SubtitleAnalysisSource,
            SubtitleKindSummary = string.IsNullOrWhiteSpace(job.SubtitleKindSummary) ? "未分析" : job.SubtitleKindSummary
        };

        HistoryEntries.Insert(0, entry);
        while (HistoryEntries.Count > 1000)
        {
            HistoryEntries.RemoveAt(HistoryEntries.Count - 1);
        }

        await _taskHistoryService.SaveAsync(HistoryEntries);
        RaiseHistoryProperties();
        NotifyCommandStateChanged();
    }

    private bool MatchesHistoryFilter(TaskHistoryEntry entry)
    {
        var matchesStatus = HistoryStatusFilter == "全部" || entry.StatusText == HistoryStatusFilter;
        var matchesDate = !HistoryDateFilter.HasValue || entry.RecordedAt.Date == HistoryDateFilter.Value.Date;
        return matchesStatus && matchesDate;
    }

    private void NotifyCommandStateChanged()
    {
        if (ChooseAudioInputCommand is AsyncRelayCommand chooseAudioInput)
        {
            chooseAudioInput.NotifyCanExecuteChanged();
        }

        if (ChooseClipInputCommand is AsyncRelayCommand chooseClipInput)
        {
            chooseClipInput.NotifyCanExecuteChanged();
        }

        if (ChoosePipOverlayCommand is RelayCommand choosePipOverlay)
        {
            choosePipOverlay.NotifyCanExecuteChanged();
        }

        if (ClearPipOverlayCommand is RelayCommand clearPipOverlay)
        {
            clearPipOverlay.NotifyCanExecuteChanged();
        }

        if (ChooseAudioMixBackgroundCommand is RelayCommand chooseAudioMixBackground)
        {
            chooseAudioMixBackground.NotifyCanExecuteChanged();
        }

        if (ClearAudioMixBackgroundCommand is RelayCommand clearAudioMixBackground)
        {
            clearAudioMixBackground.NotifyCanExecuteChanged();
        }

        if (UseSelectedJobAsAudioInputCommand is AsyncRelayCommand useSelectedJobAsAudioInput)
        {
            useSelectedJobAsAudioInput.NotifyCanExecuteChanged();
        }

        if (UseSelectedJobAsClipInputCommand is AsyncRelayCommand useSelectedJobAsClipInput)
        {
            useSelectedJobAsClipInput.NotifyCanExecuteChanged();
        }

        if (ChooseSelectedJobDanmakuCommand is RelayCommand chooseSelectedJobDanmaku)
        {
            chooseSelectedJobDanmaku.NotifyCanExecuteChanged();
        }

        if (ClearSelectedJobDanmakuCommand is RelayCommand clearSelectedJobDanmaku)
        {
            clearSelectedJobDanmaku.NotifyCanExecuteChanged();
        }

        if (OpenSelectedDanmakuCommand is RelayCommand openSelectedDanmaku)
        {
            openSelectedDanmaku.NotifyCanExecuteChanged();
        }

        if (OpenGeneratedDanmakuAssCommand is RelayCommand openGeneratedDanmakuAss)
        {
            openGeneratedDanmakuAss.NotifyCanExecuteChanged();
        }

        if (AnalyzeSelectedDanmakuCommand is AsyncRelayCommand analyzeSelectedDanmaku)
        {
            analyzeSelectedDanmaku.NotifyCanExecuteChanged();
        }

        if (ClearSelectedDanmakuExclusionsCommand is RelayCommand clearSelectedDanmakuExclusions)
        {
            clearSelectedDanmakuExclusions.NotifyCanExecuteChanged();
        }

        if (ImportSelectedDanmakuRulesCommand is AsyncRelayCommand importSelectedDanmakuRules)
        {
            importSelectedDanmakuRules.NotifyCanExecuteChanged();
        }

        if (ExportSelectedDanmakuRulesCommand is AsyncRelayCommand exportSelectedDanmakuRules)
        {
            exportSelectedDanmakuRules.NotifyCanExecuteChanged();
        }

        if (DisableFilteredDanmakuCommand is RelayCommand disableFilteredDanmaku)
        {
            disableFilteredDanmaku.NotifyCanExecuteChanged();
        }

        if (EnableFilteredDanmakuCommand is RelayCommand enableFilteredDanmaku)
        {
            enableFilteredDanmaku.NotifyCanExecuteChanged();
        }

        if (DisableDanmakuByKeywordsCommand is RelayCommand disableDanmakuByKeywords)
        {
            disableDanmakuByKeywords.NotifyCanExecuteChanged();
        }

        if (EnableDanmakuByKeywordsCommand is RelayCommand enableDanmakuByKeywords)
        {
            enableDanmakuByKeywords.NotifyCanExecuteChanged();
        }

        if (RefreshSelectedPreviewCommand is AsyncRelayCommand refreshSelectedPreview)
        {
            refreshSelectedPreview.NotifyCanExecuteChanged();
        }

        if (ExtractAudioCommand is AsyncRelayCommand extractAudio)
        {
            extractAudio.NotifyCanExecuteChanged();
        }

        if (StartAudioMixCommand is AsyncRelayCommand startAudioMix)
        {
            startAudioMix.NotifyCanExecuteChanged();
        }

        if (DetectSilenceCommand is AsyncRelayCommand detectSilence)
        {
            detectSilence.NotifyCanExecuteChanged();
        }

        if (StartFastClipCommand is AsyncRelayCommand startFastClip)
        {
            startFastClip.NotifyCanExecuteChanged();
        }

        if (StartGifPreviewCommand is AsyncRelayCommand startGifPreview)
        {
            startGifPreview.NotifyCanExecuteChanged();
        }

        if (StartPictureInPictureCommand is AsyncRelayCommand startPictureInPicture)
        {
            startPictureInPicture.NotifyCanExecuteChanged();
        }

        if (StartSpeedChangeCommand is AsyncRelayCommand startSpeedChange)
        {
            startSpeedChange.NotifyCanExecuteChanged();
        }

        if (StartReverseCommand is AsyncRelayCommand startReverse)
        {
            startReverse.NotifyCanExecuteChanged();
        }

        if (StartConcatCommand is AsyncRelayCommand startConcat)
        {
            startConcat.NotifyCanExecuteChanged();
        }

        if (GenerateAutoSegmentsCommand is RelayCommand generateAutoSegments)
        {
            generateAutoSegments.NotifyCanExecuteChanged();
        }

        if (DetectScenesCommand is AsyncRelayCommand detectScenes)
        {
            detectScenes.NotifyCanExecuteChanged();
        }

        if (DetectBlackSegmentsCommand is AsyncRelayCommand detectBlackSegments)
        {
            detectBlackSegments.NotifyCanExecuteChanged();
        }

        if (DetectFreezeSegmentsCommand is AsyncRelayCommand detectFreezeSegments)
        {
            detectFreezeSegments.NotifyCanExecuteChanged();
        }

        if (GenerateCoverCandidatesCommand is AsyncRelayCommand generateCoverCandidates)
        {
            generateCoverCandidates.NotifyCanExecuteChanged();
        }

        if (StartVerticalAdaptCommand is AsyncRelayCommand startVerticalAdapt)
        {
            startVerticalAdapt.NotifyCanExecuteChanged();
        }

        if (StartDouyinExportCommand is AsyncRelayCommand startDouyinExport)
        {
            startDouyinExport.NotifyCanExecuteChanged();
        }

        if (StartBatchDouyinExportCommand is AsyncRelayCommand startBatchDouyinExport)
        {
            startBatchDouyinExport.NotifyCanExecuteChanged();
        }

        if (StartQueueCommand is AsyncRelayCommand start)
        {
            start.NotifyCanExecuteChanged();
        }

        if (SaveSettingsCommand is AsyncRelayCommand save)
        {
            save.NotifyCanExecuteChanged();
        }

        if (CancelCommand is RelayCommand cancel)
        {
            cancel.NotifyCanExecuteChanged();
        }

        if (CancelAudioExtractionCommand is RelayCommand cancelAudioExtraction)
        {
            cancelAudioExtraction.NotifyCanExecuteChanged();
        }

        if (CancelClipCommand is RelayCommand cancelClip)
        {
            cancelClip.NotifyCanExecuteChanged();
        }

        if (CancelDouyinExportCommand is RelayCommand cancelDouyinExport)
        {
            cancelDouyinExport.NotifyCanExecuteChanged();
        }

        if (RemoveSelectedCommand is RelayCommand remove)
        {
            remove.NotifyCanExecuteChanged();
        }

        if (OpenAudioOutputDirectoryCommand is RelayCommand openAudioOutputDirectory)
        {
            openAudioOutputDirectory.NotifyCanExecuteChanged();
        }

        if (OpenAudioMixOutputDirectoryCommand is RelayCommand openAudioMixOutputDirectory)
        {
            openAudioMixOutputDirectory.NotifyCanExecuteChanged();
        }

        if (OpenClipOutputDirectoryCommand is RelayCommand openClipOutputDirectory)
        {
            openClipOutputDirectory.NotifyCanExecuteChanged();
        }

        if (OpenConcatOutputDirectoryCommand is RelayCommand openConcatOutputDirectory)
        {
            openConcatOutputDirectory.NotifyCanExecuteChanged();
        }

        if (OpenVerticalOutputDirectoryCommand is RelayCommand openVerticalOutputDirectory)
        {
            openVerticalOutputDirectory.NotifyCanExecuteChanged();
        }

        if (OpenGifOutputDirectoryCommand is RelayCommand openGifOutputDirectory)
        {
            openGifOutputDirectory.NotifyCanExecuteChanged();
        }

        if (OpenPipOutputDirectoryCommand is RelayCommand openPipOutputDirectory)
        {
            openPipOutputDirectory.NotifyCanExecuteChanged();
        }

        if (OpenVideoFxOutputDirectoryCommand is RelayCommand openVideoFxOutputDirectory)
        {
            openVideoFxOutputDirectory.NotifyCanExecuteChanged();
        }

        if (OpenDouyinOutputDirectoryCommand is RelayCommand openDouyinOutputDirectory)
        {
            openDouyinOutputDirectory.NotifyCanExecuteChanged();
        }

        if (ChooseDouyinBgmCommand is RelayCommand chooseDouyinBgm)
        {
            chooseDouyinBgm.NotifyCanExecuteChanged();
        }

        if (ClearDouyinBgmCommand is RelayCommand clearDouyinBgm)
        {
            clearDouyinBgm.NotifyCanExecuteChanged();
        }

        if (OpenSelectedOutputDirectoryCommand is RelayCommand openSelectedOutput)
        {
            openSelectedOutput.NotifyCanExecuteChanged();
        }

        if (OpenInspectionDirectoryCommand is RelayCommand openInspectionDirectory)
        {
            openInspectionDirectory.NotifyCanExecuteChanged();
        }

        if (OpenCoverCandidatesDirectoryCommand is RelayCommand openCoverCandidatesDirectory)
        {
            openCoverCandidatesDirectory.NotifyCanExecuteChanged();
        }

        if (OpenInspectionSampleCommand is RelayCommand openInspectionSample)
        {
            openInspectionSample.NotifyCanExecuteChanged();
        }

        if (CaptureSelectedFrameCommand is AsyncRelayCommand captureFrame)
        {
            captureFrame.NotifyCanExecuteChanged();
        }

        if (CaptureSelectedFrameSetCommand is AsyncRelayCommand captureFrameSet)
        {
            captureFrameSet.NotifyCanExecuteChanged();
        }

        if (ExportInspectionReportJsonCommand is AsyncRelayCommand exportInspectionJson)
        {
            exportInspectionJson.NotifyCanExecuteChanged();
        }

        if (ExportInspectionReportTextCommand is AsyncRelayCommand exportInspectionText)
        {
            exportInspectionText.NotifyCanExecuteChanged();
        }

        if (RetryFailedJobsCommand is RelayCommand retry)
        {
            retry.NotifyCanExecuteChanged();
        }

        if (ClearFinishedJobsCommand is RelayCommand clearFinished)
        {
            clearFinished.NotifyCanExecuteChanged();
        }

        if (ExportHistoryJsonCommand is AsyncRelayCommand exportJson)
        {
            exportJson.NotifyCanExecuteChanged();
        }

        if (ExportHistoryTextCommand is AsyncRelayCommand exportText)
        {
            exportText.NotifyCanExecuteChanged();
        }

        if (ClearHistoryFiltersCommand is RelayCommand clear)
        {
            clear.NotifyCanExecuteChanged();
        }

        NotifyAudioProjectCommandStateChanged();
    }

    private void OnJobsCollectionChanged(object? sender, NotifyCollectionChangedEventArgs e)
    {
        if (e.NewItems is not null)
        {
            foreach (TranscodeJob job in e.NewItems)
            {
                AttachJob(job);
            }
        }

        if (e.OldItems is not null)
        {
            foreach (TranscodeJob job in e.OldItems)
            {
                DetachJob(job);
            }
        }

        RaiseQueueSummaryProperties();
        NotifyCommandStateChanged();
    }

    private void AttachJob(TranscodeJob job)
    {
        job.PropertyChanged += JobOnPropertyChanged;
    }

    private void DetachJob(TranscodeJob job)
    {
        job.PropertyChanged -= JobOnPropertyChanged;
    }

    private void JobOnPropertyChanged(object? sender, System.ComponentModel.PropertyChangedEventArgs e)
    {
        if (e.PropertyName is nameof(TranscodeJob.Status) or nameof(TranscodeJob.Progress))
        {
            RaiseQueueSummaryProperties();
        }

        if (ReferenceEquals(sender, SelectedJob))
        {
            RaiseSelectedJobProperties();
            NotifyCommandStateChanged();
        }
    }

    private void RaiseQueueSummaryProperties()
    {
        RaisePropertyChanged(nameof(TotalJobs));
        RaisePropertyChanged(nameof(PendingJobs));
        RaisePropertyChanged(nameof(RunningJobs));
        RaisePropertyChanged(nameof(SuccessJobs));
        RaisePropertyChanged(nameof(FailedJobs));
        RaisePropertyChanged(nameof(QueueSummary));
    }

    private void RaiseHistoryProperties()
    {
        RaisePropertyChanged(nameof(FilteredHistoryEntries));
        RaisePropertyChanged(nameof(HistoryCount));
        RaisePropertyChanged(nameof(HistorySummary));
        NotifyCommandStateChanged();
    }

    private void RaiseSelectedJobProperties()
    {
        RaisePropertyChanged(nameof(SelectedJobTitle));
        RaisePropertyChanged(nameof(SelectedJobStatusText));
        RaisePropertyChanged(nameof(SelectedJobMessage));
        RaisePropertyChanged(nameof(SelectedJobInputPath));
        RaisePropertyChanged(nameof(SelectedJobOutputPath));
        RaisePropertyChanged(nameof(SelectedJobEncoder));
        RaisePropertyChanged(nameof(SelectedJobSubtitleAnalysis));
        RaisePropertyChanged(nameof(SelectedJobSubtitleKind));
        RaisePropertyChanged(nameof(SelectedJobDanmakuSource));
        RaisePropertyChanged(nameof(SelectedJobDanmakuInputPath));
        RaisePropertyChanged(nameof(SelectedJobDanmakuPreparation));
        RaisePropertyChanged(nameof(SelectedJobDanmakuXmlStats));
        RaisePropertyChanged(nameof(SelectedJobDanmakuAssPath));
        RaisePropertyChanged(nameof(SelectedJobProgressText));
    }

    private void RaiseInspectionProperties()
    {
        RaisePropertyChanged(nameof(HasInspectionSamples));
        RaisePropertyChanged(nameof(InspectionSummary));
        RaisePropertyChanged(nameof(InspectionOutputDirectory));
        RaisePropertyChanged(nameof(InspectionSource));
        RaisePropertyChanged(nameof(InspectionReportHeadline));
        RaisePropertyChanged(nameof(InspectionAttentionSummary));
    }

    private sealed class OverlayPreparationState
    {
        public bool Success { get; init; }
        public int? SubtitleStreamOrdinal { get; init; }
        public string DanmakuAssPath { get; init; } = string.Empty;
        public string DanmakuXmlPath { get; init; } = string.Empty;
        public int DanmakuXmlCommentCount { get; init; }
        public int DanmakuKeptCommentCount { get; init; }
        public string SubtitleAnalysisSource { get; init; } = string.Empty;
        public string SubtitleKindSummary { get; init; } = string.Empty;
        public string DanmakuSourceSummary { get; init; } = string.Empty;
        public string DanmakuPreparationSummary { get; init; } = string.Empty;
        public string ErrorMessage { get; init; } = string.Empty;

        public static OverlayPreparationState Fail(string errorMessage)
        {
            return new OverlayPreparationState
            {
                Success = false,
                ErrorMessage = errorMessage
            };
        }

        public static OverlayPreparationState SuccessState(
            int? subtitleStreamOrdinal,
            string danmakuAssPath,
            string danmakuXmlPath,
            int danmakuXmlCommentCount,
            int danmakuKeptCommentCount,
            string subtitleAnalysisSource,
            string subtitleKindSummary,
            string danmakuSourceSummary,
            string danmakuPreparationSummary)
        {
            return new OverlayPreparationState
            {
                Success = true,
                SubtitleStreamOrdinal = subtitleStreamOrdinal,
                DanmakuAssPath = danmakuAssPath,
                DanmakuXmlPath = danmakuXmlPath,
                DanmakuXmlCommentCount = danmakuXmlCommentCount,
                DanmakuKeptCommentCount = danmakuKeptCommentCount,
                SubtitleAnalysisSource = subtitleAnalysisSource,
                SubtitleKindSummary = subtitleKindSummary,
                DanmakuSourceSummary = danmakuSourceSummary,
                DanmakuPreparationSummary = danmakuPreparationSummary
            };
        }
    }

    private static double DetermineFrameSampleTimeSeconds(TranscodeJob job)
    {
        if (job.SourceDurationSeconds <= 0)
        {
            return 5.0;
        }

        return Math.Min(Math.Max(job.SourceDurationSeconds * 0.1, 1.0), 30.0);
    }

    private static IReadOnlyList<double> DetermineInspectionSampleTimes(TranscodeJob job)
    {
        if (job.SourceDurationSeconds <= 0)
        {
            return [1.0, 3.0, 5.0];
        }

        var duration = job.SourceDurationSeconds;
        var samples = new[]
        {
            Math.Min(Math.Max(duration * 0.10, 1.0), Math.Max(duration - 0.5, 1.0)),
            Math.Min(Math.Max(duration * 0.50, 1.0), Math.Max(duration - 0.5, 1.0)),
            Math.Min(Math.Max(duration * 0.90, 1.0), Math.Max(duration - 0.5, 1.0))
        };

        return samples
            .Distinct()
            .OrderBy(value => value)
            .ToList();
    }

    private void NotifyQueueCompleted(bool queueWasCancelled)
    {
        if (TotalJobs == 0)
        {
            return;
        }

        var title = queueWasCancelled ? "队列已中止" : "队列处理完成";
        var summary = $"总任务数：{TotalJobs}{Environment.NewLine}" +
                      $"已完成：{SuccessJobs}{Environment.NewLine}" +
                      $"失败：{FailedJobs}{Environment.NewLine}" +
                      $"已跳过：{Jobs.Count(job => job.Status == JobStatus.Skipped)}{Environment.NewLine}" +
                      $"已取消：{Jobs.Count(job => job.Status == JobStatus.Cancelled)}";

        QueueCompleted?.Invoke(title, summary);
    }

    private void SettingsOnPropertyChanged(object? sender, System.ComponentModel.PropertyChangedEventArgs e)
    {
        if (e.PropertyName is nameof(AppSettings.InputDirectory) or nameof(AppSettings.EnableDirectoryWatch) or nameof(AppSettings.StableFileWaitSeconds))
        {
            UpdateDirectoryWatcher();
        }

        if (e.PropertyName is nameof(AppSettings.OutputDirectory) or nameof(AppSettings.EnableDanmaku))
        {
            RecalculateOutputPaths();
            RaisePropertyChanged(nameof(AudioOutputDirectoryPath));
            RaisePropertyChanged(nameof(AudioMixOutputDirectoryPath));
            RaisePropertyChanged(nameof(ClipOutputDirectoryPath));
            RaisePropertyChanged(nameof(ConcatOutputDirectoryPath));
            RaisePropertyChanged(nameof(VerticalOutputDirectoryPath));
            RaisePropertyChanged(nameof(GifOutputDirectoryPath));
            RaisePropertyChanged(nameof(PipOutputDirectoryPath));
            RaisePropertyChanged(nameof(VideoFxOutputDirectoryPath));
            RaisePropertyChanged(nameof(DouyinOutputDirectoryPath));
        }

        if (e.PropertyName is nameof(AppSettings.BurnEmbeddedSubtitles) or
            nameof(AppSettings.EnableDanmaku) or
            nameof(AppSettings.DanmakuSourceMode) or
            nameof(AppSettings.DanmakuAreaMode) or
            nameof(AppSettings.DanmakuFontName) or
            nameof(AppSettings.DanmakuFontSize) or
            nameof(AppSettings.DanmakuDensity) or
            nameof(AppSettings.DanmakuTimeOffsetSeconds) or
            nameof(AppSettings.DanmakuBlockKeywords) or
            nameof(AppSettings.DanmakuFilterSpecialTypes))
        {
            SelectedPreviewImagePath = string.Empty;
            SelectedPreviewSummary = "配置已变更，请刷新叠加预览";
        }

        if (e.PropertyName == nameof(AppSettings.VideoEncoderMode) || e.PropertyName == nameof(AppSettings.Cq))
        {
            RaisePropertyChanged(nameof(SelectedClipModeSummary));
            RaisePropertyChanged(nameof(SelectedDouyinTemplateSummary));
        }

        if (e.PropertyName == nameof(AppSettings.AutoStartQueueOnWatch))
        {
            WatchSummary = BuildWatchSummary();
        }
    }

    private void UpdateDirectoryWatcher()
    {
        if (!Settings.EnableDirectoryWatch)
        {
            _directoryWatchService.Stop();
            WatchSummary = "目录监听已关闭";
            return;
        }

        _directoryWatchService.Start(
            Settings.InputDirectory,
            Settings.StableFileWaitSeconds,
            path =>
            {
                _ = System.Windows.Application.Current.Dispatcher.InvokeAsync(async () =>
                {
                    var addedCount = AddPathsCore([path]);
                    if (addedCount > 0 && Settings.AutoStartQueueOnWatch && !IsRunning && !IsAudioExtracting && !IsAudioSilenceDetecting && !IsClipRunning && !IsDouyinExporting)
                    {
                        AppendLog("检测到新稳定文件，已自动启动队列。");
                        await StartQueueAsync();
                    }
                });
            },
            AppendLog);

        WatchSummary = BuildWatchSummary();
    }

    private string BuildWatchSummary()
    {
        var autoStartText = Settings.AutoStartQueueOnWatch ? "自动开跑已开启" : "仅自动入队";
        return $"监听输入目录：{Settings.InputDirectory} | 稳定等待 {Settings.StableFileWaitSeconds} 秒 | {autoStartText}";
    }

    private void OpenInspectionDirectory()
    {
        if (Directory.Exists(_inspectionOutputDirectory))
        {
            _userDialogService.OpenFolder(_inspectionOutputDirectory);
        }
    }

    private void OpenInspectionSample(string? path)
    {
        if (!string.IsNullOrWhiteSpace(path) && File.Exists(path))
        {
            _userDialogService.OpenFile(path);
        }
    }

    private async Task ExportInspectionReportAsync(string format)
    {
        if (_inspectionReport is null || SelectedJob is null)
        {
            return;
        }

        var extension = format.ToLowerInvariant();
        var fileName = $"{Path.GetFileNameWithoutExtension(SelectedJob.InputPath)}-inspection-report.{extension}";
        var filter = extension == "json"
            ? "JSON 文件 (*.json)|*.json"
            : "文本文件 (*.txt)|*.txt";
        var savePath = _userDialogService.PickSaveFile(
            extension == "json" ? "导出巡检报告 JSON" : "导出巡检报告 TXT",
            filter,
            fileName,
            _inspectionOutputDirectory);

        if (string.IsNullOrWhiteSpace(savePath))
        {
            return;
        }

        await _frameInspectionService.ExportAsync(_inspectionReport, savePath, extension);
        StatusMessage = $"巡检报告已导出：{savePath}";
        AppendLog($"巡检报告已导出：{savePath}");
    }

    private void OnInspectionSamplesCollectionChanged(object? sender, NotifyCollectionChangedEventArgs e)
    {
        RaiseInspectionProperties();
        NotifyCommandStateChanged();
    }

    public void Dispose()
    {
        Settings.PropertyChanged -= SettingsOnPropertyChanged;
        InspectionSamples.CollectionChanged -= OnInspectionSamplesCollectionChanged;
        _audioExtractionCancellationTokenSource?.Cancel();
        _audioExtractionCancellationTokenSource?.Dispose();
        _clipCancellationTokenSource?.Cancel();
        _clipCancellationTokenSource?.Dispose();
        _douyinExportCancellationTokenSource?.Cancel();
        _douyinExportCancellationTokenSource?.Dispose();
        _directoryWatchService.Dispose();
    }
}
