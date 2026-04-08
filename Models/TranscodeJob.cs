namespace AnimeTranscoder.Models;

public sealed class TranscodeJob : ObservableObject
{
    private JobStatus _status = JobStatus.Pending;
    private double _progress;
    private string _speed = string.Empty;
    private string _message = string.Empty;
    private int? _subtitleStreamOrdinal;
    private string _encoderUsed = string.Empty;
    private string _outputPath = string.Empty;
    private double _sourceDurationSeconds;
    private string _subtitleAnalysisSource = string.Empty;
    private string _subtitleKindSummary = string.Empty;
    private string _danmakuInputPath = string.Empty;
    private string _danmakuSourceSummary = string.Empty;
    private string _danmakuPreparationSummary = string.Empty;
    private string _danmakuXmlPath = string.Empty;
    private string _danmakuAssPath = string.Empty;
    private int _danmakuXmlCommentCount;
    private int _danmakuKeptCommentCount;
    private string _danmakuExcludedCommentKeys = string.Empty;

    public Guid Id { get; init; } = Guid.NewGuid();
    public string InputPath { get; init; } = string.Empty;
    
    public string OutputPath
    {
        get => _outputPath;
        set => SetProperty(ref _outputPath, value);
    }

    public string FileName => Path.GetFileName(InputPath);

    public JobStatus Status
    {
        get => _status;
        set
        {
            if (SetProperty(ref _status, value))
            {
                RaisePropertyChanged(nameof(StatusText));
            }
        }
    }

    public double Progress
    {
        get => _progress;
        set => SetProperty(ref _progress, value);
    }

    public string Speed
    {
        get => _speed;
        set => SetProperty(ref _speed, value);
    }

    public string Message
    {
        get => _message;
        set => SetProperty(ref _message, value);
    }

    public int? SubtitleStreamOrdinal
    {
        get => _subtitleStreamOrdinal;
        set => SetProperty(ref _subtitleStreamOrdinal, value);
    }

    public string EncoderUsed
    {
        get => _encoderUsed;
        set => SetProperty(ref _encoderUsed, value);
    }

    public double SourceDurationSeconds
    {
        get => _sourceDurationSeconds;
        set => SetProperty(ref _sourceDurationSeconds, value);
    }

    public string SubtitleAnalysisSource
    {
        get => _subtitleAnalysisSource;
        set => SetProperty(ref _subtitleAnalysisSource, value);
    }

    public string SubtitleKindSummary
    {
        get => _subtitleKindSummary;
        set => SetProperty(ref _subtitleKindSummary, value);
    }

    public string DanmakuInputPath
    {
        get => _danmakuInputPath;
        set => SetProperty(ref _danmakuInputPath, value);
    }

    public string DanmakuSourceSummary
    {
        get => _danmakuSourceSummary;
        set => SetProperty(ref _danmakuSourceSummary, value);
    }

    public string DanmakuPreparationSummary
    {
        get => _danmakuPreparationSummary;
        set => SetProperty(ref _danmakuPreparationSummary, value);
    }

    public string DanmakuXmlPath
    {
        get => _danmakuXmlPath;
        set => SetProperty(ref _danmakuXmlPath, value);
    }

    public string DanmakuAssPath
    {
        get => _danmakuAssPath;
        set => SetProperty(ref _danmakuAssPath, value);
    }

    public int DanmakuXmlCommentCount
    {
        get => _danmakuXmlCommentCount;
        set => SetProperty(ref _danmakuXmlCommentCount, value);
    }

    public int DanmakuKeptCommentCount
    {
        get => _danmakuKeptCommentCount;
        set => SetProperty(ref _danmakuKeptCommentCount, value);
    }

    public string DanmakuExcludedCommentKeys
    {
        get => _danmakuExcludedCommentKeys;
        set => SetProperty(ref _danmakuExcludedCommentKeys, value);
    }

    public string StatusText => Status switch
    {
        JobStatus.Pending => "等待中",
        JobStatus.Probing => "分析中",
        JobStatus.Ready => "已就绪",
        JobStatus.Running => "转码中",
        JobStatus.Success => "已完成",
        JobStatus.Failed => "失败",
        JobStatus.Skipped => "已跳过",
        JobStatus.Cancelled => "已取消",
        _ => Status.ToString()
    };
}
