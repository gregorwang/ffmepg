namespace AnimeTranscoder.Models;

public sealed class AppSettings : ObservableObject
{
    private string _inputDirectory = string.Empty;
    private string _outputDirectory = string.Empty;
    private string _subtitlePreference = "chs";
    private string _videoEncoderMode = "auto";
    private bool _overwriteExisting;
    private bool _deleteSourceAfterSuccess;
    private bool _enableDirectoryWatch = true;
    private bool _autoStartQueueOnWatch = true;
    private int _stableFileWaitSeconds = 20;
    private string _nvencPreset = "p4";
    private int _cq = 21;
    private int _audioBitrateKbps = 192;
    private bool _preferStereoAudio = true;
    private bool _enableFaststart = true;
    private int _outputSafetyMarginMb = 2048;
    private bool _burnEmbeddedSubtitles = true;
    private bool _enableDanmaku;
    private string _danmakuSourceMode = DanmakuSourceModes.BilibiliAuto;
    private string _danmakuMappingPath = string.Empty;
    private string _danmakuFontName = "Microsoft YaHei";
    private int _danmakuFontSize = 46;
    private double _danmakuDensity = 0.65;
    private double _danmakuTimeOffsetSeconds;
    private string _danmakuBlockKeywords = string.Empty;
    private bool _danmakuFilterSpecialTypes = true;
    private string _danmakuAreaMode = DanmakuAreaModes.UpperHalf;
    private string _subtitleSourceMode = SubtitleSourceModes.Embedded;

    public string InputDirectory
    {
        get => _inputDirectory;
        set => SetProperty(ref _inputDirectory, value);
    }

    public string OutputDirectory
    {
        get => _outputDirectory;
        set => SetProperty(ref _outputDirectory, value);
    }

    public string SubtitlePreference
    {
        get => _subtitlePreference;
        set => SetProperty(ref _subtitlePreference, value);
    }

    public string VideoEncoderMode
    {
        get => _videoEncoderMode;
        set => SetProperty(ref _videoEncoderMode, value);
    }

    public bool OverwriteExisting
    {
        get => _overwriteExisting;
        set => SetProperty(ref _overwriteExisting, value);
    }

    public bool DeleteSourceAfterSuccess
    {
        get => _deleteSourceAfterSuccess;
        set => SetProperty(ref _deleteSourceAfterSuccess, value);
    }

    public bool EnableDirectoryWatch
    {
        get => _enableDirectoryWatch;
        set => SetProperty(ref _enableDirectoryWatch, value);
    }

    public bool AutoStartQueueOnWatch
    {
        get => _autoStartQueueOnWatch;
        set => SetProperty(ref _autoStartQueueOnWatch, value);
    }

    public int StableFileWaitSeconds
    {
        get => _stableFileWaitSeconds;
        set => SetProperty(ref _stableFileWaitSeconds, value);
    }

    public string NvencPreset
    {
        get => _nvencPreset;
        set => SetProperty(ref _nvencPreset, value);
    }

    public int Cq
    {
        get => _cq;
        set => SetProperty(ref _cq, value);
    }

    public int AudioBitrateKbps
    {
        get => _audioBitrateKbps;
        set => SetProperty(ref _audioBitrateKbps, value);
    }

    public bool PreferStereoAudio
    {
        get => _preferStereoAudio;
        set => SetProperty(ref _preferStereoAudio, value);
    }

    public bool EnableFaststart
    {
        get => _enableFaststart;
        set => SetProperty(ref _enableFaststart, value);
    }

    public int OutputSafetyMarginMb
    {
        get => _outputSafetyMarginMb;
        set => SetProperty(ref _outputSafetyMarginMb, value);
    }

    public bool BurnEmbeddedSubtitles
    {
        get => _burnEmbeddedSubtitles;
        set => SetProperty(ref _burnEmbeddedSubtitles, value);
    }

    public bool EnableDanmaku
    {
        get => _enableDanmaku;
        set => SetProperty(ref _enableDanmaku, value);
    }

    public string DanmakuSourceMode
    {
        get => _danmakuSourceMode;
        set => SetProperty(ref _danmakuSourceMode, value);
    }

    public string DanmakuAreaMode
    {
        get => _danmakuAreaMode;
        set => SetProperty(ref _danmakuAreaMode, value);
    }

    public string SubtitleSourceMode
    {
        get => _subtitleSourceMode;
        set => SetProperty(ref _subtitleSourceMode, value);
    }

    public string DanmakuMappingPath
    {
        get => _danmakuMappingPath;
        set => SetProperty(ref _danmakuMappingPath, value);
    }

    public string DanmakuFontName
    {
        get => _danmakuFontName;
        set => SetProperty(ref _danmakuFontName, value);
    }

    public int DanmakuFontSize
    {
        get => _danmakuFontSize;
        set => SetProperty(ref _danmakuFontSize, value);
    }

    public double DanmakuDensity
    {
        get => _danmakuDensity;
        set => SetProperty(ref _danmakuDensity, value);
    }

    public double DanmakuTimeOffsetSeconds
    {
        get => _danmakuTimeOffsetSeconds;
        set => SetProperty(ref _danmakuTimeOffsetSeconds, value);
    }

    public string DanmakuBlockKeywords
    {
        get => _danmakuBlockKeywords;
        set => SetProperty(ref _danmakuBlockKeywords, value);
    }

    public bool DanmakuFilterSpecialTypes
    {
        get => _danmakuFilterSpecialTypes;
        set => SetProperty(ref _danmakuFilterSpecialTypes, value);
    }

    public static AppSettings CreateDefault(string workspaceRoot)
    {
        return new AppSettings
        {
            InputDirectory = workspaceRoot,
            OutputDirectory = Path.Combine(workspaceRoot, "mp4_hardsub_chs"),
            SubtitlePreference = "chs",
            VideoEncoderMode = "auto",
            OverwriteExisting = false,
            DeleteSourceAfterSuccess = false,
            EnableDirectoryWatch = true,
            AutoStartQueueOnWatch = true,
            StableFileWaitSeconds = 20,
            NvencPreset = "p4",
            Cq = 21,
            AudioBitrateKbps = 192,
            PreferStereoAudio = true,
            EnableFaststart = true,
            OutputSafetyMarginMb = 2048,
            BurnEmbeddedSubtitles = true,
            EnableDanmaku = false,
            DanmakuSourceMode = DanmakuSourceModes.BilibiliAuto,
            DanmakuMappingPath = Path.Combine(workspaceRoot, "Config", "anime-danmaku-mappings.json"),
            DanmakuFontName = "Microsoft YaHei",
            DanmakuFontSize = 46,
            DanmakuDensity = 0.65,
            DanmakuTimeOffsetSeconds = 0,
            DanmakuBlockKeywords = string.Empty,
            DanmakuFilterSpecialTypes = true,
            DanmakuAreaMode = DanmakuAreaModes.UpperHalf,
            SubtitleSourceMode = SubtitleSourceModes.Embedded
        };
    }
}
