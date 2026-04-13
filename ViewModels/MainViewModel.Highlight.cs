using System.Collections.ObjectModel;
using System.Windows.Input;
using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;
using AnimeTranscoder.Services;

namespace AnimeTranscoder.ViewModels;

public sealed partial class MainViewModel
{
    private HighlightScoringService _highlightScoringService = null!;
    private CancellationTokenSource? _highlightCancellationTokenSource;
    private string _highlightInputPath = string.Empty;
    private string _highlightProbeSummary = "请选择媒体文件以开始高光分析";
    private string _highlightStatusMessage = "尚未开始";
    private string _highlightWindowSecondsText = "10";
    private string _highlightTopNText = "6";
    private string _highlightSceneThresholdText = "0.20";
    private double _highlightProgress;
    private string _highlightSpeed = string.Empty;
    private bool _isHighlightRunning;
    private HighlightCandidate? _selectedHighlightCandidate;
    private TimeSpan _highlightSourceDuration;

    public ICommand ChooseHighlightInputCommand { get; private set; } = null!;
    public ICommand UseSelectedJobAsHighlightInputCommand { get; private set; } = null!;
    public ICommand RunHighlightAnalysisCommand { get; private set; } = null!;
    public ICommand CancelHighlightCommand { get; private set; } = null!;
    public ICommand ExportHighlightVerticalCommand { get; private set; } = null!;
    public ICommand ExportHighlightGifCommand { get; private set; } = null!;
    public ICommand ExportHighlightCoverCommand { get; private set; } = null!;
    public ICommand ExportHighlightAllCommand { get; private set; } = null!;
    public ICommand OpenHighlightOutputDirectoryCommand { get; private set; } = null!;

    public ObservableCollection<HighlightCandidate> HighlightCandidates { get; } = [];

    public string HighlightInputPath
    {
        get => _highlightInputPath;
        private set => SetProperty(ref _highlightInputPath, value);
    }

    public string HighlightProbeSummary
    {
        get => _highlightProbeSummary;
        private set => SetProperty(ref _highlightProbeSummary, value);
    }

    public string HighlightStatusMessage
    {
        get => _highlightStatusMessage;
        private set => SetProperty(ref _highlightStatusMessage, value);
    }

    public string HighlightWindowSecondsText
    {
        get => _highlightWindowSecondsText;
        set => SetProperty(ref _highlightWindowSecondsText, value);
    }

    public string HighlightTopNText
    {
        get => _highlightTopNText;
        set => SetProperty(ref _highlightTopNText, value);
    }

    public string HighlightSceneThresholdText
    {
        get => _highlightSceneThresholdText;
        set => SetProperty(ref _highlightSceneThresholdText, value);
    }

    public double HighlightProgress
    {
        get => _highlightProgress;
        private set => SetProperty(ref _highlightProgress, value);
    }

    public string HighlightSpeed
    {
        get => _highlightSpeed;
        private set => SetProperty(ref _highlightSpeed, value);
    }

    public bool IsHighlightRunning
    {
        get => _isHighlightRunning;
        private set => SetProperty(ref _isHighlightRunning, value);
    }

    public HighlightCandidate? SelectedHighlightCandidate
    {
        get => _selectedHighlightCandidate;
        set => SetProperty(ref _selectedHighlightCandidate, value);
    }

    public string HighlightOutputDirectoryPath => Path.Combine(Settings.OutputDirectory, "highlights");

    private void InitializeHighlightFeature(HighlightScoringService highlightScoringService)
    {
        _highlightScoringService = highlightScoringService;

        ChooseHighlightInputCommand = new AsyncRelayCommand(ChooseHighlightInputAsync, CanChooseHighlightInput);
        UseSelectedJobAsHighlightInputCommand = new AsyncRelayCommand(UseSelectedJobAsHighlightInputAsync,
            () => CanChooseHighlightInput() && SelectedJob is not null && File.Exists(SelectedJob.InputPath));
        RunHighlightAnalysisCommand = new AsyncRelayCommand(RunHighlightAnalysisAsync, CanRunHighlightAnalysis);
        CancelHighlightCommand = new RelayCommand(_ => CancelHighlight(), _ => IsHighlightRunning);
        ExportHighlightVerticalCommand = new AsyncRelayCommand(ExportHighlightVerticalAsync, CanExportHighlight);
        ExportHighlightGifCommand = new AsyncRelayCommand(ExportHighlightGifAsync, CanExportHighlight);
        ExportHighlightCoverCommand = new AsyncRelayCommand(ExportHighlightCoverAsync, CanExportHighlight);
        ExportHighlightAllCommand = new AsyncRelayCommand(ExportHighlightAllAsync, CanExportHighlight);
        OpenHighlightOutputDirectoryCommand = new RelayCommand(
            _ => _userDialogService.OpenFolder(HighlightOutputDirectoryPath),
            _ => Directory.Exists(HighlightOutputDirectoryPath));
    }

    private bool CanChooseHighlightInput() =>
        !IsRunning && !IsAudioExtracting && !IsAudioSilenceDetecting &&
        !IsClipRunning && !IsDouyinExporting && !IsHighlightRunning;

    private bool CanRunHighlightAnalysis() =>
        CanChooseHighlightInput() && !string.IsNullOrWhiteSpace(HighlightInputPath) && File.Exists(HighlightInputPath);

    private bool CanExportHighlight() =>
        CanChooseHighlightInput() && SelectedHighlightCandidate is not null &&
        !string.IsNullOrWhiteSpace(HighlightInputPath) && File.Exists(HighlightInputPath);

    private async Task ChooseHighlightInputAsync()
    {
        if (!CanChooseHighlightInput()) return;

        var path = _userDialogService.PickFile(
            "选择高光分析源",
            "媒体文件 (*.mkv;*.mp4;*.mov;*.avi;*.ts;*.m2ts;*.webm)|*.mkv;*.mp4;*.mov;*.avi;*.ts;*.m2ts;*.webm|所有文件 (*.*)|*.*",
            Settings.InputDirectory);
        if (string.IsNullOrWhiteSpace(path)) return;

        await LoadHighlightSourceAsync(path);
    }

    private async Task UseSelectedJobAsHighlightInputAsync()
    {
        if (SelectedJob is null || !File.Exists(SelectedJob.InputPath)) return;
        await LoadHighlightSourceAsync(SelectedJob.InputPath);
    }

    private async Task LoadHighlightSourceAsync(string inputPath)
    {
        HighlightInputPath = inputPath;
        HighlightProbeSummary = "正在探测媒体信息...";
        HighlightStatusMessage = "正在探测...";

        try
        {
            var probe = await _ffprobeService.ProbeAsync(inputPath, CancellationToken.None);
            _highlightSourceDuration = probe?.Duration ?? TimeSpan.Zero;
            HighlightProbeSummary = probe is not null
                ? $"{Path.GetFileName(inputPath)} | 时长 {FormatTimeSpan(probe.Duration)} | {probe.AnalysisSource}"
                : $"{Path.GetFileName(inputPath)} | 探测失败";
            HighlightStatusMessage = "已就绪，可点击「一键分析」";
        }
        catch (Exception ex)
        {
            HighlightProbeSummary = $"探测失败：{ex.Message}";
            HighlightStatusMessage = "探测失败";
        }

        NotifyHighlightCommandStateChanged();
    }

    private async Task RunHighlightAnalysisAsync()
    {
        if (!CanRunHighlightAnalysis()) return;

        if (!double.TryParse(HighlightWindowSecondsText, out var windowSeconds) || windowSeconds < 2 || windowSeconds > 60)
        {
            HighlightStatusMessage = "窗口时长必须在 2-60 秒之间";
            return;
        }

        if (!int.TryParse(HighlightTopNText, out var topN) || topN < 1 || topN > 30)
        {
            HighlightStatusMessage = "候选数量必须在 1-30 之间";
            return;
        }

        if (!double.TryParse(HighlightSceneThresholdText, out var sceneThreshold) || sceneThreshold < 0.01 || sceneThreshold > 1.0)
        {
            HighlightStatusMessage = "场景阈值必须在 0.01-1.0 之间";
            return;
        }

        IsHighlightRunning = true;
        HighlightProgress = 0;
        HighlightSpeed = string.Empty;
        HighlightCandidates.Clear();
        _highlightCancellationTokenSource = new CancellationTokenSource();

        StatusMessage = "正在执行高光分析...";
        HighlightStatusMessage = "Step 1/4: 场景切换检测...";
        AppendLog($"开始高光分析：{HighlightInputPath}");

        try
        {
            var cancellationToken = _highlightCancellationTokenSource.Token;

            // Step 1: Scene detection
            HighlightProgress = 5;
            var sceneCutPoints = await _videoClipService.DetectScenesAsync(
                HighlightInputPath, sceneThreshold, cancellationToken);
            HighlightProgress = 25;
            AppendLog($"场景检测完成：{sceneCutPoints.Count} 个切点");

            cancellationToken.ThrowIfCancellationRequested();

            // Step 2: Volume analysis
            HighlightStatusMessage = "Step 2/4: 音量变化分析...";
            var volumeSegments = await _videoClipService.DetectVolumeSegmentsAsync(
                HighlightInputPath, windowSeconds, cancellationToken);
            HighlightProgress = 50;
            AppendLog($"音量分析完成：{volumeSegments.Count} 个窗口");

            cancellationToken.ThrowIfCancellationRequested();

            // Step 3: Black segment detection
            HighlightStatusMessage = "Step 3/4: 黑场检测...";
            var blackSegments = await _videoClipService.DetectBlackSegmentsAsync(
                HighlightInputPath, 0.98, 0.10, 0.20, cancellationToken);
            HighlightProgress = 70;
            AppendLog($"黑场检测完成：{blackSegments.Count} 个黑场");

            cancellationToken.ThrowIfCancellationRequested();

            // Step 4: Freeze detection + Scoring
            HighlightStatusMessage = "Step 4/4: 冻帧检测 + 评分...";
            var freezeSegments = await _videoClipService.DetectFreezeSegmentsAsync(
                HighlightInputPath, 0.003, 0.50, cancellationToken);
            HighlightProgress = 85;
            AppendLog($"冻帧检测完成：{freezeSegments.Count} 个冻帧");

            cancellationToken.ThrowIfCancellationRequested();

            // Scoring
            var totalDuration = _highlightSourceDuration.TotalSeconds;
            var candidates = _highlightScoringService.Score(
                totalDuration, sceneCutPoints, volumeSegments,
                blackSegments, freezeSegments, windowSeconds, topN);

            foreach (var candidate in candidates)
            {
                HighlightCandidates.Add(candidate);
            }

            HighlightProgress = 100;
            HighlightSpeed = "done";
            HighlightStatusMessage = candidates.Count > 0
                ? $"分析完成！已生成 {candidates.Count} 个高光候选"
                : "分析完成，但未找到符合条件的高光片段";
            StatusMessage = "高光分析完成";
            AppendLog($"高光分析完成：{candidates.Count} 个候选 | 场景 {sceneCutPoints.Count} | 音量窗口 {volumeSegments.Count} | 黑场 {blackSegments.Count} | 冻帧 {freezeSegments.Count}");
        }
        catch (OperationCanceledException)
        {
            HighlightStatusMessage = "高光分析已取消";
            StatusMessage = "高光分析已取消";
            AppendLog("高光分析已取消。");
        }
        catch (Exception ex)
        {
            HighlightStatusMessage = $"高光分析失败：{ex.Message}";
            StatusMessage = "高光分析失败";
            AppendLog($"高光分析异常：{ex.Message}");
            AppFileLogger.Write("HighlightAnalysis", $"异常：{ex}");
        }
        finally
        {
            IsHighlightRunning = false;
            _highlightCancellationTokenSource?.Dispose();
            _highlightCancellationTokenSource = null;
            NotifyHighlightCommandStateChanged();
            NotifyCommandStateChanged();
        }
    }

    private void CancelHighlight()
    {
        _highlightCancellationTokenSource?.Cancel();
        HighlightStatusMessage = "正在取消...";
    }

    private async Task ExportHighlightVerticalAsync()
    {
        if (!CanExportHighlight() || SelectedHighlightCandidate is null) return;
        var candidate = SelectedHighlightCandidate;

        // First clip the segment, then convert to vertical
        var clipOutputDir = EnsureHighlightOutputDirectory();
        var clipFileName = $"{Path.GetFileNameWithoutExtension(HighlightInputPath)}-hl{candidate.Rank}-vertical.mp4";
        var clipPath = Path.Combine(clipOutputDir, clipFileName);
        var encoder = _hardwareDetectionService.ResolveVideoEncoder(Settings.VideoEncoderMode, _isNvencAvailable);

        IsHighlightRunning = true;
        HighlightProgress = 0;
        HighlightStatusMessage = $"正在导出高光 #{candidate.Rank} 竖屏...";
        _highlightCancellationTokenSource = new CancellationTokenSource();

        try
        {
            // First clip the segment
            var tempClipPath = Path.Combine(clipOutputDir, $"_temp_hl{candidate.Rank}.mp4");
            var clipResult = await _videoClipService.PreciseClipAsync(
                HighlightInputPath, tempClipPath,
                TimeSpan.FromSeconds(candidate.StartSeconds),
                TimeSpan.FromSeconds(candidate.DurationSeconds),
                encoder, Settings.NvencPreset, Settings.Cq, Settings.AudioBitrateKbps,
                OnHighlightExportProgress,
                _highlightCancellationTokenSource.Token);

            if (!clipResult.Success)
            {
                HighlightStatusMessage = $"片段裁切失败：{clipResult.ErrorMessage}";
                return;
            }

            HighlightProgress = 50;
            // Convert to vertical
            var vertResult = await _videoClipService.ConvertToVerticalAsync(
                tempClipPath, clipPath,
                VerticalMode.BlurBackground, encoder, Settings.NvencPreset,
                Settings.Cq, Settings.AudioBitrateKbps,
                candidate.DurationSeconds,
                OnHighlightExportProgress,
                _highlightCancellationTokenSource.Token);

            // Clean up temp file
            try { File.Delete(tempClipPath); } catch { }

            HighlightProgress = 100;
            HighlightStatusMessage = vertResult.Success
                ? $"竖屏导出完成：{clipFileName}"
                : $"竖屏导出失败：{vertResult.ErrorMessage}";
            AppendLog($"高光竖屏导出：{clipPath} | {(vertResult.Success ? "成功" : "失败")}");
        }
        catch (OperationCanceledException)
        {
            HighlightStatusMessage = "导出已取消";
        }
        catch (Exception ex)
        {
            HighlightStatusMessage = $"导出失败：{ex.Message}";
        }
        finally
        {
            IsHighlightRunning = false;
            _highlightCancellationTokenSource?.Dispose();
            _highlightCancellationTokenSource = null;
            NotifyHighlightCommandStateChanged();
        }
    }

    private async Task ExportHighlightGifAsync()
    {
        if (!CanExportHighlight() || SelectedHighlightCandidate is null) return;
        var candidate = SelectedHighlightCandidate;

        var outputDir = EnsureHighlightOutputDirectory();
        var fileName = $"{Path.GetFileNameWithoutExtension(HighlightInputPath)}-hl{candidate.Rank}.gif";
        var outputPath = Path.Combine(outputDir, fileName);

        IsHighlightRunning = true;
        HighlightProgress = 0;
        HighlightStatusMessage = $"正在导出高光 #{candidate.Rank} GIF...";
        _highlightCancellationTokenSource = new CancellationTokenSource();

        try
        {
            var result = await _videoClipService.GenerateGifPreviewAsync(
                HighlightInputPath, outputPath,
                TimeSpan.FromSeconds(candidate.StartSeconds),
                TimeSpan.FromSeconds(Math.Min(candidate.DurationSeconds, 15.0)),
                OnHighlightExportProgress,
                _highlightCancellationTokenSource.Token);

            HighlightProgress = 100;
            HighlightStatusMessage = result.Success
                ? $"GIF 导出完成：{fileName}"
                : $"GIF 导出失败：{result.ErrorMessage}";
            AppendLog($"高光 GIF 导出：{outputPath} | {(result.Success ? "成功" : "失败")}");
        }
        catch (OperationCanceledException)
        {
            HighlightStatusMessage = "导出已取消";
        }
        catch (Exception ex)
        {
            HighlightStatusMessage = $"导出失败：{ex.Message}";
        }
        finally
        {
            IsHighlightRunning = false;
            _highlightCancellationTokenSource?.Dispose();
            _highlightCancellationTokenSource = null;
            NotifyHighlightCommandStateChanged();
        }
    }

    private async Task ExportHighlightCoverAsync()
    {
        if (!CanExportHighlight() || SelectedHighlightCandidate is null) return;
        var candidate = SelectedHighlightCandidate;

        var outputDir = EnsureHighlightOutputDirectory();
        var filePrefix = $"{Path.GetFileNameWithoutExtension(HighlightInputPath)}-hl{candidate.Rank}-cover";
        var captureTime = candidate.StartSeconds + candidate.DurationSeconds / 2.0;

        IsHighlightRunning = true;
        HighlightProgress = 0;
        HighlightStatusMessage = $"正在导出高光 #{candidate.Rank} 封面截图...";
        _highlightCancellationTokenSource = new CancellationTokenSource();

        try
        {
            var captureResult = await _nativeMediaCoreService.CaptureDiagnosticFramesAsync(
                HighlightInputPath, outputDir, filePrefix,
                [captureTime],
                _highlightCancellationTokenSource.Token);

            HighlightProgress = 100;
            HighlightStatusMessage = captureResult.Success
                ? $"封面截图完成：{filePrefix}"
                : $"封面截图失败：{captureResult.Message}";
            AppendLog($"高光封面导出：{outputDir} | {(captureResult.Success ? "成功" : "失败")}");
        }
        catch (OperationCanceledException)
        {
            HighlightStatusMessage = "导出已取消";
        }
        catch (Exception ex)
        {
            HighlightStatusMessage = $"导出失败：{ex.Message}";
        }
        finally
        {
            IsHighlightRunning = false;
            _highlightCancellationTokenSource?.Dispose();
            _highlightCancellationTokenSource = null;
            NotifyHighlightCommandStateChanged();
        }
    }

    private async Task ExportHighlightAllAsync()
    {
        if (!CanExportHighlight() || SelectedHighlightCandidate is null) return;
        var candidate = SelectedHighlightCandidate;

        IsHighlightRunning = true;
        HighlightProgress = 0;
        HighlightStatusMessage = $"正在一键导出高光 #{candidate.Rank}（GIF + 竖屏 + 封面）...";

        try
        {
            HighlightStatusMessage = $"[1/3] 正在导出 GIF...";
            await ExportHighlightGifAsync();

            HighlightStatusMessage = $"[2/3] 正在导出竖屏...";
            await ExportHighlightVerticalAsync();

            HighlightStatusMessage = $"[3/3] 正在导出封面...";
            await ExportHighlightCoverAsync();

            HighlightProgress = 100;
            HighlightStatusMessage = $"高光 #{candidate.Rank} 全部导出完成";
            StatusMessage = "高光一键导出完成";
            AppendLog($"高光 #{candidate.Rank} 一键导出完成");
        }
        catch (Exception ex)
        {
            HighlightStatusMessage = $"一键导出失败：{ex.Message}";
        }
    }

    private string EnsureHighlightOutputDirectory()
    {
        var dir = Path.Combine(HighlightOutputDirectoryPath,
            Path.GetFileNameWithoutExtension(HighlightInputPath));
        Directory.CreateDirectory(dir);
        return dir;
    }

    private void OnHighlightExportProgress(double progress, string speed)
    {
        _ = System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
        {
            HighlightProgress = Math.Round(progress, 2);
            if (!string.IsNullOrWhiteSpace(speed) &&
                !string.Equals(speed, "done", StringComparison.OrdinalIgnoreCase))
            {
                HighlightSpeed = speed;
            }
        });
    }

    private void NotifyHighlightCommandStateChanged()
    {
        RaisePropertyChanged(nameof(HighlightOutputDirectoryPath));

        if (ChooseHighlightInputCommand is AsyncRelayCommand choose)
            choose.NotifyCanExecuteChanged();
        if (UseSelectedJobAsHighlightInputCommand is AsyncRelayCommand useJob)
            useJob.NotifyCanExecuteChanged();
        if (RunHighlightAnalysisCommand is AsyncRelayCommand run)
            run.NotifyCanExecuteChanged();
        if (CancelHighlightCommand is RelayCommand cancel)
            cancel.NotifyCanExecuteChanged();
        if (ExportHighlightVerticalCommand is AsyncRelayCommand vert)
            vert.NotifyCanExecuteChanged();
        if (ExportHighlightGifCommand is AsyncRelayCommand gif)
            gif.NotifyCanExecuteChanged();
        if (ExportHighlightCoverCommand is AsyncRelayCommand cover)
            cover.NotifyCanExecuteChanged();
        if (ExportHighlightAllCommand is AsyncRelayCommand all)
            all.NotifyCanExecuteChanged();
        if (OpenHighlightOutputDirectoryCommand is RelayCommand openDir)
            openDir.NotifyCanExecuteChanged();
    }
}
