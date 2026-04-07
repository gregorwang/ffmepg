using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class DanmakuBurnCommandBuilder
{
    private readonly FfmpegCommandBuilder _ffmpegCommandBuilder;

    public DanmakuBurnCommandBuilder(FfmpegCommandBuilder ffmpegCommandBuilder)
    {
        _ffmpegCommandBuilder = ffmpegCommandBuilder;
    }

    public IReadOnlyList<string> BuildArguments(
        string inputPath,
        string outputPath,
        string assPath,
        AppSettings settings,
        string videoEncoder)
    {
        return _ffmpegCommandBuilder.BuildExternalAssArguments(inputPath, outputPath, assPath, settings, videoEncoder);
    }
}
