using AnimeTranscoder.Services;
using AnimeTranscoder.ViewModels;
using MessageBox = System.Windows.MessageBox;

namespace AnimeTranscoder.Views;

public partial class MainWindow : System.Windows.Window
{
    public MainWindow()
    {
        InitializeComponent();

        var ffmpegCommandBuilder = new FfmpegCommandBuilder();
        var ffprobeService = new FfprobeService();
        var taskHistoryService = new TaskHistoryService();
        var nativeMediaCoreService = new NativeMediaCoreService();
        var directoryWatchService = new DirectoryWatchService();
        var ffmpegRunner = new FfmpegRunner(ffmpegCommandBuilder);
        var overlayFramePreviewService = new OverlayFramePreviewService(ffmpegCommandBuilder);
        var storagePreflightService = new StoragePreflightService();
        var danmakuCacheService = new DanmakuCacheService();
        var danmakuAssGeneratorService = new DanmakuAssGeneratorService(danmakuCacheService);
        var danmakuExclusionRuleService = new DanmakuExclusionRuleService();
        var bilibiliBangumiClient = new BilibiliBangumiClient(danmakuCacheService);
        DataContext = new MainViewModel(
            new JsonSettingsService(),
            taskHistoryService,
            new UserDialogService(),
            ffprobeService,
            new SubtitleSelectionService(),
            new HardwareDetectionService(),
            new OutputValidationService(ffprobeService, nativeMediaCoreService),
            storagePreflightService,
            nativeMediaCoreService,
            directoryWatchService,
            ffmpegRunner,
            new FrameInspectionService(),
            new AudioExtractionService(ffmpegRunner, new AudioCommandBuilder()),
            new VideoClipService(ffmpegRunner, new ClipCommandBuilder()),
            new DouyinExportService(ffmpegRunner, new DouyinCommandBuilder()),
            new DanmakuPreparationService(
                new AnimeEpisodeParserService(),
                new DanmakuMappingConfigService(),
                new BangumiMappingService(bilibiliBangumiClient),
                new BilibiliCidResolverService(),
                new DanmakuXmlService(danmakuCacheService),
                danmakuAssGeneratorService),
            new DanmakuBurnCommandBuilder(ffmpegCommandBuilder),
            danmakuAssGeneratorService,
            danmakuExclusionRuleService,
            overlayFramePreviewService);

        if (DataContext is MainViewModel viewModel)
        {
            viewModel.QueueCompleted += OnQueueCompleted;
        }

        Closed += OnClosed;
    }

    private void Window_DragEnter(object sender, System.Windows.DragEventArgs e)
    {
        if (DataContext is MainViewModel viewModel)
        {
            viewModel.IsDropTargetActive = e.Data.GetDataPresent(System.Windows.DataFormats.FileDrop);
        }
    }

    private void Window_DragLeave(object sender, System.Windows.DragEventArgs e)
    {
        if (DataContext is MainViewModel viewModel)
        {
            viewModel.IsDropTargetActive = false;
        }
    }

    private void Window_DragOver(object sender, System.Windows.DragEventArgs e)
    {
        var acceptsDrop = e.Data.GetDataPresent(System.Windows.DataFormats.FileDrop);
        e.Effects = acceptsDrop ? System.Windows.DragDropEffects.Copy : System.Windows.DragDropEffects.None;
        e.Handled = true;

        if (DataContext is MainViewModel viewModel)
        {
            viewModel.IsDropTargetActive = acceptsDrop;
        }
    }

    private void Window_Drop(object sender, System.Windows.DragEventArgs e)
    {
        if (DataContext is not MainViewModel viewModel)
        {
            return;
        }

        if (e.Data.GetData(System.Windows.DataFormats.FileDrop) is string[] paths)
        {
            viewModel.IsDropTargetActive = false;
            viewModel.AddPaths(paths);
        }
    }

    private void OnQueueCompleted(string title, string summary)
    {
        _ = Dispatcher.InvokeAsync(() =>
        {
            MessageBox.Show(this, summary, title, System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Information);
        });
    }

    private void OnClosed(object? sender, EventArgs e)
    {
        if (DataContext is IDisposable disposable)
        {
            disposable.Dispose();
        }
    }
}
