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
