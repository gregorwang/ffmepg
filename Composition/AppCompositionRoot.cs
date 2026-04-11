using AnimeTranscoder.Services;
using AnimeTranscoder.ViewModels;
using AnimeTranscoder.Workflows;

namespace AnimeTranscoder.Composition;

public sealed class AppCompositionRoot
{
    public MainViewModel CreateMainViewModel()
    {
        var ffmpegCommandBuilder = new FfmpegCommandBuilder();
        var ffprobeService = new FfprobeService();
        var taskHistoryService = new TaskHistoryService();
        var nativeMediaCoreService = new NativeMediaCoreService();
        var directoryWatchService = new DirectoryWatchService();
        var ffmpegRunner = new FfmpegRunner(ffmpegCommandBuilder);
        var overlayFramePreviewService = new OverlayFramePreviewService(ffmpegCommandBuilder);
        var storagePreflightService = new StoragePreflightService();
        var subtitleSelectionService = new SubtitleSelectionService();
        var hardwareDetectionService = new HardwareDetectionService();
        var outputValidationService = new OutputValidationService(ffprobeService, nativeMediaCoreService);
        var danmakuBurnCommandBuilder = new DanmakuBurnCommandBuilder(ffmpegCommandBuilder);
        var danmakuCacheService = new DanmakuCacheService();
        var danmakuAssGeneratorService = new DanmakuAssGeneratorService(danmakuCacheService);
        var danmakuExclusionRuleService = new DanmakuExclusionRuleService();
        var bilibiliBangumiClient = new BilibiliBangumiClient(danmakuCacheService);
        var audioCommandBuilder = new AudioCommandBuilder();
        var audioExtractionService = new AudioExtractionService(ffmpegRunner, audioCommandBuilder);
        var audioProcessingWorkflow = new AudioProcessingWorkflow(audioExtractionService);
        var transcodeQueueWorkflow = new TranscodeQueueWorkflow(
            outputValidationService,
            storagePreflightService,
            nativeMediaCoreService,
            ffprobeService,
            hardwareDetectionService,
            danmakuBurnCommandBuilder,
            ffmpegRunner);
        var projectFileService = new ProjectFileService();
        var transcriptDocumentService = new TranscriptDocumentService();
        var selectionDocumentService = new SelectionDocumentService();
        var projectAudioWorkflow = new ProjectAudioWorkflow(
            projectFileService,
            transcriptDocumentService,
            selectionDocumentService,
            audioExtractionService,
            new AudioSelectionRenderService(ffmpegRunner, ffprobeService),
            ffprobeService);

        return new MainViewModel(
            new JsonSettingsService(),
            taskHistoryService,
            new UserDialogService(),
            ffprobeService,
            subtitleSelectionService,
            hardwareDetectionService,
            outputValidationService,
            storagePreflightService,
            nativeMediaCoreService,
            directoryWatchService,
            ffmpegRunner,
            new FrameInspectionService(),
            audioExtractionService,
            audioProcessingWorkflow,
            transcodeQueueWorkflow,
            new VideoClipService(ffmpegRunner, new ClipCommandBuilder()),
            new DouyinExportService(ffmpegRunner, new DouyinCommandBuilder()),
            new DanmakuPreparationService(
                new AnimeEpisodeParserService(),
                new DanmakuMappingConfigService(),
                new BangumiMappingService(bilibiliBangumiClient),
                new BilibiliCidResolverService(),
                new DanmakuXmlService(danmakuCacheService),
                danmakuAssGeneratorService),
            danmakuBurnCommandBuilder,
            danmakuAssGeneratorService,
            danmakuExclusionRuleService,
            overlayFramePreviewService,
            projectFileService,
            transcriptDocumentService,
            selectionDocumentService,
            projectAudioWorkflow);
    }
}
