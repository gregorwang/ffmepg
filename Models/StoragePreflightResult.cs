namespace AnimeTranscoder.Models;

public sealed class StoragePreflightResult
{
    public bool HasEnoughSpace { get; init; }
    public string Message { get; init; } = string.Empty;
    public long RequiredBytes { get; init; }
    public long AvailableBytes { get; init; }
    public string DriveName { get; init; } = string.Empty;
}
