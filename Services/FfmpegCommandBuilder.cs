using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class FfmpegCommandBuilder
{
    public IReadOnlyList<string> BuildArguments(TranscodeJob job, AppSettings settings, string videoEncoder)
    {
        return BuildArguments(
            job.InputPath,
            job.OutputPath,
            job.SubtitleStreamOrdinal,
            null,
            settings,
            videoEncoder);
    }

    public IReadOnlyList<string> BuildArguments(
        string inputPath,
        string outputPath,
        int? subtitleStreamOrdinal,
        string? assPath,
        AppSettings settings,
        string videoEncoder)
    {
        if (subtitleStreamOrdinal is null && string.IsNullOrWhiteSpace(assPath))
        {
            throw new InvalidOperationException("At least one subtitle or danmaku source must be set before building ffmpeg arguments.");
        }

        return BuildArgumentsCore(
            inputPath,
            outputPath,
            BuildVideoFilter(inputPath, subtitleStreamOrdinal, assPath),
            settings,
            videoEncoder);
    }

    public IReadOnlyList<string> BuildExternalAssArguments(
        string inputPath,
        string outputPath,
        string assPath,
        AppSettings settings,
        string videoEncoder)
    {
        return BuildArgumentsCore(
            inputPath,
            outputPath,
            BuildVideoFilter(inputPath, null, assPath),
            settings,
            videoEncoder);
    }

    public string BuildVideoFilter(string inputPath, int? subtitleStreamOrdinal, string? assPath)
    {
        var filters = new List<string>();

        if (subtitleStreamOrdinal is not null)
        {
            filters.Add($"subtitles='{ConvertToFilterPath(inputPath)}':si={subtitleStreamOrdinal.Value}");
        }

        if (!string.IsNullOrWhiteSpace(assPath))
        {
            filters.Add($"ass='{ConvertToFilterPath(assPath)}'");
        }

        return string.Join(",", filters);
    }

    private static IReadOnlyList<string> BuildArgumentsCore(
        string inputPath,
        string outputPath,
        string videoFilter,
        AppSettings settings,
        string videoEncoder)
    {
        var args = new List<string>
        {
            "-y",
            "-hide_banner",
            "-nostats",
            "-progress",
            "pipe:1"
        };

        if (string.Equals(videoEncoder, "h264_nvenc", StringComparison.OrdinalIgnoreCase))
        {
            args.Add("-hwaccel");
            args.Add("cuda");
        }

        args.Add("-i");
        args.Add(inputPath);
        args.Add("-vf");
        args.Add(videoFilter);
        args.Add("-map");
        args.Add("0:v:0");
        args.Add("-map");
        args.Add("0:a:0?");
        args.Add("-map_chapters");
        args.Add("-1");
        args.Add("-c:v");
        args.Add(videoEncoder);

        if (string.Equals(videoEncoder, "h264_nvenc", StringComparison.OrdinalIgnoreCase))
        {
            args.Add("-preset");
            args.Add(settings.NvencPreset);
            args.Add("-tune");
            args.Add("hq");
            args.Add("-cq");
            args.Add(settings.Cq.ToString());
            args.Add("-b:v");
            args.Add("0");
        }
        else
        {
            args.Add("-preset");
            args.Add("medium");
            args.Add("-crf");
            args.Add(settings.Cq.ToString());
        }

        args.Add("-pix_fmt");
        args.Add("yuv420p");
        args.Add("-c:a");
        args.Add("aac");
        args.Add("-profile:a");
        args.Add("aac_low");
        args.Add("-ac");
        args.Add(settings.PreferStereoAudio ? "2" : "6");
        args.Add("-ar");
        args.Add("48000");
        args.Add("-b:a");
        args.Add($"{settings.AudioBitrateKbps}k");

        if (settings.EnableFaststart)
        {
            args.Add("-movflags");
            args.Add("+faststart");
        }

        args.Add("-sn");
        args.Add(outputPath);

        return args;
    }

    private static string ConvertToFilterPath(string path)
    {
        var value = path.Replace('\\', '/');
        value = value.Replace(":", "\\:");
        value = value.Replace("'", "\\'");
        return value;
    }
}
