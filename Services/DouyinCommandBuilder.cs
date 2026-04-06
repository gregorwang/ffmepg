using System.Globalization;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class DouyinCommandBuilder
{
    public IReadOnlyList<string> BuildExportArguments(
        string inputPath,
        string outputPath,
        string? bgmPath,
        DouyinTemplatePreset preset,
        int? subtitleStreamOrdinal,
        string titleText,
        string watermarkText,
        double sourceVolume,
        double bgmVolume,
        bool sourceHasAudio,
        double totalDurationSeconds,
        string videoEncoder,
        string nvencPreset,
        int cq,
        int audioBitrateKbps)
    {
        var hasBgm = !string.IsNullOrWhiteSpace(bgmPath) && File.Exists(bgmPath);
        var filterParts = new List<string>();
        var currentVideoLabel = BuildBaseVideoFilter(filterParts, preset, inputPath, subtitleStreamOrdinal);
        var drawtextFontOption = BuildDrawtextFontOption();

        if (!string.IsNullOrWhiteSpace(titleText))
        {
            var nextLabel = "vtitle";
            filterParts.Add($"[{currentVideoLabel}]drawtext={drawtextFontOption}text='{EscapeDrawtext(titleText)}':fontsize=60:fontcolor=white:borderw=3:bordercolor=black:x=64:y=96[{nextLabel}]");
            currentVideoLabel = nextLabel;
        }

        if (!string.IsNullOrWhiteSpace(watermarkText))
        {
            var nextLabel = "vwatermark";
            filterParts.Add($"[{currentVideoLabel}]drawtext={drawtextFontOption}text='{EscapeDrawtext(watermarkText)}':fontsize=32:fontcolor=white@0.78:borderw=2:bordercolor=black:x=w-tw-48:y=h-th-48[{nextLabel}]");
            currentVideoLabel = nextLabel;
        }

        filterParts.Add($"[{currentVideoLabel}]fps=30,format=yuv420p[vout]");

        var hasOutputAudio = false;
        if (sourceHasAudio && hasBgm)
        {
            filterParts.Add($"[0:a:0]volume={FormatNumber(sourceVolume)}[amain]");
            filterParts.Add($"[1:a:0]volume={FormatNumber(bgmVolume)}[abgm]");
            filterParts.Add("[amain][abgm]amix=inputs=2:duration=first:dropout_transition=2[aout]");
            hasOutputAudio = true;
        }
        else if (sourceHasAudio)
        {
            filterParts.Add($"[0:a:0]volume={FormatNumber(sourceVolume)}[aout]");
            hasOutputAudio = true;
        }
        else if (hasBgm)
        {
            filterParts.Add($"[1:a:0]volume={FormatNumber(bgmVolume)}[aout]");
            hasOutputAudio = true;
        }

        var args = new List<string>
        {
            "-y",
            "-hide_banner",
            "-nostats",
            "-progress",
            "pipe:1",
            "-i",
            inputPath
        };

        if (hasBgm)
        {
            args.AddRange([
                "-stream_loop",
                "-1",
                "-i",
                bgmPath!
            ]);
        }

        args.AddRange([
            "-t",
            totalDurationSeconds.ToString("0.000", CultureInfo.InvariantCulture),
            "-filter_complex",
            string.Join(';', filterParts),
            "-map",
            "[vout]",
            "-map_chapters",
            "-1",
            "-sn",
            "-c:v",
            videoEncoder
        ]);

        if (hasOutputAudio)
        {
            args.AddRange([
                "-map",
                "[aout]"
            ]);
        }

        if (string.Equals(videoEncoder, "h264_nvenc", StringComparison.OrdinalIgnoreCase))
        {
            args.AddRange([
                "-preset", nvencPreset,
                "-tune", "hq",
                "-cq", cq.ToString(CultureInfo.InvariantCulture),
                "-b:v", "0"
            ]);
        }
        else
        {
            args.AddRange([
                "-preset", "medium",
                "-crf", cq.ToString(CultureInfo.InvariantCulture)
            ]);
        }

        args.AddRange([
            "-pix_fmt", "yuv420p",
            "-r", "30"
        ]);

        if (hasOutputAudio)
        {
            args.AddRange([
                "-c:a", "aac",
                "-profile:a", "aac_low",
                "-b:a", $"{audioBitrateKbps}k",
                "-ac", "2",
                "-ar", "48000"
            ]);
        }
        else
        {
            args.Add("-an");
        }

        args.AddRange([
            "-movflags", "+faststart",
            outputPath
        ]);

        return args;
    }

    private static string BuildBaseVideoFilter(
        ICollection<string> filterParts,
        DouyinTemplatePreset preset,
        string inputPath,
        int? subtitleStreamOrdinal)
    {
        var sourceLabel = "0:v";
        if (subtitleStreamOrdinal is not null)
        {
            filterParts.Add($"[0:v]subtitles='{ConvertToSubtitleFilterPath(inputPath)}':si={subtitleStreamOrdinal.Value}[vsub]");
            sourceLabel = "vsub";
        }

        if (preset == DouyinTemplatePreset.CropTitleWatermark)
        {
            filterParts.Add($"[{sourceLabel}]crop=ih*9/16:ih,scale=1080:1920,setsar=1[vbase]");
            return "vbase";
        }

        filterParts.Add($"[{sourceLabel}]scale=1080:1920,setsar=1,boxblur=20:5[bg]");
        filterParts.Add($"[{sourceLabel}]scale=1080:1920:force_original_aspect_ratio=decrease,setsar=1[main]");
        filterParts.Add("[bg][main]overlay=(W-w)/2:(H-h)/2,setsar=1[vbase]");
        return "vbase";
    }

    private static string EscapeDrawtext(string text)
    {
        return text
            .Replace(@"\", @"\\", StringComparison.Ordinal)
            .Replace(":", @"\:", StringComparison.Ordinal)
            .Replace("'", @"\'", StringComparison.Ordinal)
            .Replace("%", @"\%", StringComparison.Ordinal)
            .Replace(",", @"\,", StringComparison.Ordinal)
            .Replace("[", @"\[", StringComparison.Ordinal)
            .Replace("]", @"\]", StringComparison.Ordinal);
    }

    private static string FormatNumber(double value)
    {
        return value.ToString("0.###", CultureInfo.InvariantCulture);
    }

    private static string BuildDrawtextFontOption()
    {
        foreach (var candidate in GetCandidateFontPaths())
        {
            if (File.Exists(candidate))
            {
                return $"fontfile='{EscapeFontPath(candidate)}':";
            }
        }

        return string.Empty;
    }

    private static IEnumerable<string> GetCandidateFontPaths()
    {
        var windowsDirectory = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        if (string.IsNullOrWhiteSpace(windowsDirectory))
        {
            yield break;
        }

        yield return Path.Combine(windowsDirectory, "Fonts", "msyh.ttc");
        yield return Path.Combine(windowsDirectory, "Fonts", "msyhbd.ttc");
        yield return Path.Combine(windowsDirectory, "Fonts", "simhei.ttf");
    }

    private static string EscapeFontPath(string path)
    {
        return path
            .Replace(@"\", "/", StringComparison.Ordinal)
            .Replace(":", @"\:", StringComparison.Ordinal);
    }

    private static string ConvertToSubtitleFilterPath(string path)
    {
        return path
            .Replace('\\', '/')
            .Replace(":", "\\:", StringComparison.Ordinal)
            .Replace("'", "\\'", StringComparison.Ordinal);
    }
}
