namespace AnimeTranscoder.Models;

public sealed class EditableDanmakuComment : ObservableObject
{
    private bool _isEnabled = true;

    public string Key { get; init; } = string.Empty;
    public double TimeSeconds { get; init; }
    public int Mode { get; init; }
    public string Content { get; init; } = string.Empty;

    public bool IsEnabled
    {
        get => _isEnabled;
        set => SetProperty(ref _isEnabled, value);
    }
}
