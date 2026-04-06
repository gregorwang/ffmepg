using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class OutputValidationService
{
    private readonly FfprobeService _ffprobeService;
    private readonly NativeMediaCoreService _nativeMediaCoreService;

    public OutputValidationService(FfprobeService ffprobeService, NativeMediaCoreService nativeMediaCoreService)
    {
        _ffprobeService = ffprobeService;
        _nativeMediaCoreService = nativeMediaCoreService;
    }

    public async Task<bool> HasMatchingDurationAsync(
        string inputPath,
        string outputPath,
        int toleranceSeconds = 5,
        CancellationToken cancellationToken = default)
    {
        var result = await ValidateAsync(inputPath, outputPath, toleranceSeconds, cancellationToken);
        return result.IsMatch;
    }

    public async Task<OutputValidationResult> ValidateAsync(
        string inputPath,
        string outputPath,
        int toleranceSeconds = 5,
        CancellationToken cancellationToken = default)
    {
        if (!File.Exists(outputPath))
        {
            return new OutputValidationResult
            {
                IsMatch = false,
                IsFallback = false,
                Source = "filesystem",
                Message = "输出文件不存在",
                OutputReadable = false
            };
        }

        var nativeResult = await _nativeMediaCoreService.ValidateOutputAsync(inputPath, outputPath, toleranceSeconds, cancellationToken);
        if (nativeResult is not null)
        {
            AppFileLogger.Write("OutputValidationService", $"已通过原生模块完成输出校验，差值 {nativeResult.DifferenceSeconds:0.000}s");
            return nativeResult;
        }

        MediaProbeResult? input;
        MediaProbeResult? output;

        try
        {
            input = await _ffprobeService.ProbeAsync(inputPath, cancellationToken);
            output = await _ffprobeService.ProbeAsync(outputPath, cancellationToken);
        }
        catch (Exception ex)
        {
            return new OutputValidationResult
            {
                IsMatch = false,
                IsFallback = true,
                Source = "ffprobe",
                Message = $"ffprobe 无法读取输出文件：{ex.Message}",
                OutputReadable = false
            };
        }

        if (input is null || output is null)
        {
            return new OutputValidationResult
            {
                IsMatch = false,
                IsFallback = true,
                Source = "ffprobe",
                Message = "ffprobe 输出校验失败",
                OutputReadable = false
            };
        }

        var primaryAudio = output.AudioTracks.FirstOrDefault();
        var hasReadableStreams = output.Duration > TimeSpan.Zero;
        var difference = Math.Abs((input.Duration - output.Duration).TotalSeconds);
        var audioLayoutLooksCompatible = primaryAudio is null ||
                                         primaryAudio.Channels <= 2 ||
                                         string.Equals(primaryAudio.ChannelLayout, "stereo", StringComparison.OrdinalIgnoreCase);
        var isMatch = hasReadableStreams &&
                      difference <= toleranceSeconds &&
                      audioLayoutLooksCompatible;
        var message = !hasReadableStreams
            ? "输出文件可探测但流信息异常"
            : !audioLayoutLooksCompatible
                ? $"输出音轨兼容性风险：{primaryAudio?.CodecName} {primaryAudio?.ChannelSummary}"
                : "已通过 ffprobe 完成输出校验";

        return new OutputValidationResult
        {
            IsMatch = isMatch,
            IsFallback = true,
            Source = "ffprobe",
            Message = message,
            OutputReadable = hasReadableStreams,
            OutputAudioCodec = primaryAudio?.CodecName ?? string.Empty,
            OutputAudioChannels = primaryAudio?.Channels ?? 0,
            OutputAudioChannelLayout = primaryAudio?.ChannelLayout ?? string.Empty,
            InputDurationSeconds = input.Duration.TotalSeconds,
            OutputDurationSeconds = output.Duration.TotalSeconds,
            DifferenceSeconds = difference
        };
    }
}
