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
        int? subtitleStreamOrdinal,
        AppSettings settings,
        string videoEncoder)
    {
        return _ffmpegCommandBuilder.BuildArguments(
            inputPath,
            outputPath,
            subtitleStreamOrdinal,
            assPath,
            settings,
            videoEncoder);
    }
}
