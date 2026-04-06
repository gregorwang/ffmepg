using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class StoragePreflightService
{
    private const long MinimumEstimatedOutputBytes = 512L * 1024 * 1024;

    public StoragePreflightResult ValidateOutputPath(
        string inputPath,
        string outputPath,
        AppSettings settings)
    {
        var outputRoot = Path.GetPathRoot(outputPath);
        if (string.IsNullOrWhiteSpace(outputRoot))
        {
            return new StoragePreflightResult
            {
                HasEnoughSpace = false,
                Message = "无法识别输出盘符。"
            };
        }

        var drive = new DriveInfo(outputRoot);
        if (!drive.IsReady)
        {
            return new StoragePreflightResult
            {
                HasEnoughSpace = false,
                DriveName = drive.Name,
                Message = $"输出盘 {drive.Name} 不可用。"
            };
        }

        var inputSizeBytes = File.Exists(inputPath) ? new FileInfo(inputPath).Length : 0L;
        var estimatedOutputBytes = Math.Max(inputSizeBytes, MinimumEstimatedOutputBytes);
        var rewriteMultiplier = settings.EnableFaststart &&
                                string.Equals(Path.GetExtension(outputPath), ".mp4", StringComparison.OrdinalIgnoreCase)
            ? 2L
            : 1L;
        var safetyMarginBytes = Math.Max(256L * 1024 * 1024, settings.OutputSafetyMarginMb * 1024L * 1024L);
        var requiredBytes = checked((estimatedOutputBytes * rewriteMultiplier) + safetyMarginBytes);
        var availableBytes = drive.AvailableFreeSpace;

        return new StoragePreflightResult
        {
            HasEnoughSpace = availableBytes >= requiredBytes,
            DriveName = drive.Name,
            RequiredBytes = requiredBytes,
            AvailableBytes = availableBytes,
            Message = availableBytes >= requiredBytes
                ? $"输出盘空间检查通过：{drive.Name} 可用 {FormatBytes(availableBytes)}，预计至少需要 {FormatBytes(requiredBytes)}。"
                : $"输出盘空间不足：{drive.Name} 可用 {FormatBytes(availableBytes)}，预计至少需要 {FormatBytes(requiredBytes)}。"
        };
    }

    private static string FormatBytes(long bytes)
    {
        return $"{bytes / 1024d / 1024d / 1024d:0.##} GB";
    }
}
