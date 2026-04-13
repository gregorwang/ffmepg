using System.Globalization;
using System.Text;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class ClipCommandBuilder
{
    public IReadOnlyList<string> BuildFastClipArguments(
        string inputPath,
        string outputPath,
        TimeSpan startTime,
        TimeSpan duration)
    {
        return
        [
            "-y",
            "-hide_banner",
            "-nostats",
            "-progress",
            "pipe:1",
            "-ss",
            FormatTime(startTime),
            "-i",
            inputPath,
            "-t",
            duration.TotalSeconds.ToString("0.000", CultureInfo.InvariantCulture),
            "-map",
            "0",
            "-c",
            "copy",
            "-avoid_negative_ts",
            "1",
            outputPath
        ];
    }

    public IReadOnlyList<string> BuildPreciseClipArguments(
        string inputPath,
        string outputPath,
        TimeSpan startTime,
        TimeSpan duration,
        string videoEncoder,
        string nvencPreset,
        int cq,
        int audioBitrateKbps)
    {
        var args = new List<string>
        {
            "-y",
            "-hide_banner",
            "-nostats",
            "-progress",
            "pipe:1",
            "-i",
            inputPath,
            "-ss",
            FormatTime(startTime),
            "-t",
            duration.TotalSeconds.ToString("0.000", CultureInfo.InvariantCulture),
            "-map",
            "0:v:0?",
            "-map",
            "0:a:0?",
            "-map_chapters",
            "-1",
            "-c:v",
            videoEncoder
        };

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
            "-c:a", "aac",
            "-profile:a", "aac_low",
            "-ac", "2",
            "-ar", "48000",
            "-b:a", $"{audioBitrateKbps}k",
            "-sn"
        ]);

        if (string.Equals(Path.GetExtension(outputPath), ".mp4", StringComparison.OrdinalIgnoreCase))
        {
            args.AddRange(["-movflags", "+faststart"]);
        }

        args.Add(outputPath);
        return args;
    }

    public IReadOnlyList<string> BuildVerticalAdaptArguments(
        string inputPath,
        string outputPath,
        VerticalMode mode,
        string videoEncoder,
        string nvencPreset,
        int cq,
        int audioBitrateKbps)
    {
        var args = new List<string>
        {
            "-y",
            "-hide_banner",
            "-nostats",
            "-progress",
            "pipe:1",
            "-i",
            inputPath,
            "-map_chapters",
            "-1"
        };

        if (mode == VerticalMode.CropCenter)
        {
            args.AddRange([
                "-map",
                "0:v:0?",
                "-map",
                "0:a:0?",
                "-vf",
                "crop=ih*9/16:ih,scale=1080:1920,setsar=1"
            ]);
        }
        else
        {
            args.AddRange([
                "-filter_complex",
                "[0:v]scale=1080:1920,setsar=1,boxblur=20:5[bg];[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,setsar=1[main];[bg][main]overlay=(W-w)/2:(H-h)/2,setsar=1[vout]",
                "-map",
                "[vout]",
                "-map",
                "0:a:0?"
            ]);
        }

        args.AddRange([
            "-c:v", videoEncoder
        ]);

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
            "-c:a", "aac",
            "-profile:a", "aac_low",
            "-ac", "2",
            "-ar", "48000",
            "-b:a", $"{audioBitrateKbps}k",
            "-movflags", "+faststart",
            "-sn",
            outputPath
        ]);

        return args;
    }

    public IReadOnlyList<string> BuildGifPreviewArguments(
        string inputPath,
        string outputPath,
        TimeSpan startTime,
        TimeSpan duration)
    {
        return
        [
            "-y",
            "-hide_banner",
            "-nostats",
            "-progress",
            "pipe:1",
            "-ss",
            FormatTime(startTime),
            "-t",
            duration.TotalSeconds.ToString("0.000", CultureInfo.InvariantCulture),
            "-i",
            inputPath,
            "-filter_complex",
            "fps=12,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer",
            "-an",
            "-sn",
            outputPath
        ];
    }

    public IReadOnlyList<string> BuildSpeedChangeArguments(
        string inputPath,
        string outputPath,
        TimeSpan startTime,
        TimeSpan duration,
        double speedFactor,
        bool includeAudio,
        string videoEncoder,
        string nvencPreset,
        int cq,
        int audioBitrateKbps)
    {
        var filterParts = new List<string>
        {
            $"[0:v:0]setpts={FormatSeconds(1d / speedFactor)}*PTS,setsar=1[vout]"
        };

        if (includeAudio)
        {
            filterParts.Add($"[0:a:0]{BuildAtempoFilter(speedFactor)}[aout]");
        }

        var args = new List<string>
        {
            "-y",
            "-hide_banner",
            "-nostats",
            "-progress",
            "pipe:1",
            "-i",
            inputPath,
            "-ss",
            FormatTime(startTime),
            "-t",
            duration.TotalSeconds.ToString("0.000", CultureInfo.InvariantCulture),
            "-filter_complex",
            string.Join(';', filterParts),
            "-map",
            "[vout]",
            "-map_chapters",
            "-1",
            "-c:v",
            videoEncoder
        };

        if (includeAudio)
        {
            args.AddRange(["-map", "[aout]"]);
        }

        AppendVideoEncodingArguments(args, videoEncoder, nvencPreset, cq);
        args.AddRange(["-pix_fmt", "yuv420p"]);

        if (includeAudio)
        {
            args.AddRange([
                "-c:a", "aac",
                "-profile:a", "aac_low",
                "-ac", "2",
                "-ar", "48000",
                "-b:a", $"{audioBitrateKbps}k"
            ]);
        }
        else
        {
            args.Add("-an");
        }

        args.Add("-sn");

        if (string.Equals(Path.GetExtension(outputPath), ".mp4", StringComparison.OrdinalIgnoreCase))
        {
            args.AddRange(["-movflags", "+faststart"]);
        }

        args.Add(outputPath);
        return args;
    }

    public IReadOnlyList<string> BuildReverseArguments(
        string inputPath,
        string outputPath,
        TimeSpan startTime,
        TimeSpan duration,
        bool includeAudio,
        string videoEncoder,
        string nvencPreset,
        int cq,
        int audioBitrateKbps)
    {
        var filterParts = new List<string>
        {
            "[0:v:0]reverse,setsar=1[vout]"
        };

        if (includeAudio)
        {
            filterParts.Add("[0:a:0]areverse[aout]");
        }

        var args = new List<string>
        {
            "-y",
            "-hide_banner",
            "-nostats",
            "-progress",
            "pipe:1",
            "-i",
            inputPath,
            "-ss",
            FormatTime(startTime),
            "-t",
            duration.TotalSeconds.ToString("0.000", CultureInfo.InvariantCulture),
            "-filter_complex",
            string.Join(';', filterParts),
            "-map",
            "[vout]",
            "-map_chapters",
            "-1",
            "-c:v",
            videoEncoder
        };

        if (includeAudio)
        {
            args.AddRange(["-map", "[aout]"]);
        }

        AppendVideoEncodingArguments(args, videoEncoder, nvencPreset, cq);
        args.AddRange(["-pix_fmt", "yuv420p"]);

        if (includeAudio)
        {
            args.AddRange([
                "-c:a", "aac",
                "-profile:a", "aac_low",
                "-ac", "2",
                "-ar", "48000",
                "-b:a", $"{audioBitrateKbps}k"
            ]);
        }
        else
        {
            args.Add("-an");
        }

        args.Add("-sn");

        if (string.Equals(Path.GetExtension(outputPath), ".mp4", StringComparison.OrdinalIgnoreCase))
        {
            args.AddRange(["-movflags", "+faststart"]);
        }

        args.Add(outputPath);
        return args;
    }

    public IReadOnlyList<string> BuildPictureInPictureArguments(
        string inputPath,
        string overlayPath,
        string outputPath,
        PipCorner corner,
        double overlayScale,
        string videoEncoder,
        string nvencPreset,
        int cq,
        int audioBitrateKbps)
    {
        var overlayPosition = corner switch
        {
            PipCorner.TopLeft => "32:32",
            PipCorner.TopRight => "W-w-32:32",
            PipCorner.BottomLeft => "32:H-h-32",
            _ => "W-w-32:H-h-32"
        };

        var filterComplex =
            $"[1:v][0:v]scale2ref=w='trunc(main_w*{FormatSeconds(overlayScale)}/2)*2':h=-2[pip][base];" +
            $"[base][pip]overlay={overlayPosition},setsar=1[vout]";

        var args = new List<string>
        {
            "-y",
            "-hide_banner",
            "-nostats",
            "-progress",
            "pipe:1",
            "-i",
            inputPath,
            "-i",
            overlayPath,
            "-filter_complex",
            filterComplex,
            "-map",
            "[vout]",
            "-map",
            "0:a:0?",
            "-map_chapters",
            "-1",
            "-c:v",
            videoEncoder
        };

        AppendVideoEncodingArguments(args, videoEncoder, nvencPreset, cq);
        args.AddRange([
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-profile:a", "aac_low",
            "-ac", "2",
            "-ar", "48000",
            "-b:a", $"{audioBitrateKbps}k",
            "-sn"
        ]);

        if (string.Equals(Path.GetExtension(outputPath), ".mp4", StringComparison.OrdinalIgnoreCase))
        {
            args.AddRange(["-movflags", "+faststart"]);
        }

        args.Add(outputPath);
        return args;
    }

    public string BuildConcatFilterComplex(
        IReadOnlyList<ClipConcatSegment> segments,
        bool includeAudio)
    {
        ArgumentNullException.ThrowIfNull(segments);

        if (segments.Count == 0)
        {
            throw new ArgumentException("至少需要一个待拼接片段。", nameof(segments));
        }

        var filterParts = new List<string>(segments.Count * 2 + 1);
        var concatInputs = new StringBuilder();

        for (var index = 0; index < segments.Count; index++)
        {
            var segment = segments[index];
            var start = FormatSeconds(segment.Start.TotalSeconds);
            var end = FormatSeconds(segment.End.TotalSeconds);

            filterParts.Add($"[0:v:0]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{index}]");
            concatInputs.Append($"[v{index}]");

            if (includeAudio)
            {
                filterParts.Add($"[0:a:0]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{index}]");
                concatInputs.Append($"[a{index}]");
            }
        }

        var audioOutputLabel = includeAudio ? "[aout]" : string.Empty;
        filterParts.Add($"{concatInputs}concat=n={segments.Count}:v=1:a={(includeAudio ? 1 : 0)}[vout]{audioOutputLabel}");
        return string.Join(';', filterParts);
    }

    public IReadOnlyList<string> BuildConcatArguments(
        string inputPath,
        string outputPath,
        IReadOnlyList<ClipConcatSegment> segments,
        bool includeAudio,
        string videoEncoder,
        string nvencPreset,
        int cq,
        int audioBitrateKbps,
        string? filterComplexScriptPath = null)
    {
        ArgumentNullException.ThrowIfNull(segments);

        if (segments.Count == 0)
        {
            throw new ArgumentException("至少需要一个待拼接片段。", nameof(segments));
        }

        var filterComplex = BuildConcatFilterComplex(segments, includeAudio);

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

        if (string.IsNullOrWhiteSpace(filterComplexScriptPath))
        {
            args.Add("-filter_complex");
            args.Add(filterComplex);
        }
        else
        {
            args.Add("-filter_complex_script");
            args.Add(filterComplexScriptPath);
        }

        args.AddRange([
            "-map",
            "[vout]"
        ]);

        if (includeAudio)
        {
            args.AddRange([
                "-map",
                "[aout]"
            ]);
        }

        args.AddRange([
            "-map_chapters",
            "-1",
            "-c:v",
            videoEncoder
        ]);

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
            "-sn"
        ]);

        if (includeAudio)
        {
            args.AddRange([
                "-c:a", "aac",
                "-profile:a", "aac_low",
                "-ac", "2",
                "-ar", "48000",
                "-b:a", $"{audioBitrateKbps}k"
            ]);
        }
        else
        {
            args.Add("-an");
        }

        if (string.Equals(Path.GetExtension(outputPath), ".mp4", StringComparison.OrdinalIgnoreCase))
        {
            args.AddRange(["-movflags", "+faststart"]);
        }

        args.Add(outputPath);
        return args;
    }

    public IReadOnlyList<string> BuildSceneDetectArguments(string inputPath, double threshold)
    {
        return
        [
            "-hide_banner",
            "-i",
            inputPath,
            "-map",
            "0:v:0",
            "-vf",
            $"select='gt(scene,{FormatSeconds(threshold)})',showinfo",
            "-an",
            "-sn",
            "-f",
            "null",
            "-"
        ];
    }

    public IReadOnlyList<string> BuildBlackDetectArguments(
        string inputPath,
        double pictureThreshold,
        double pixelThreshold,
        double minimumDuration)
    {
        return
        [
            "-hide_banner",
            "-i",
            inputPath,
            "-map",
            "0:v:0",
            "-vf",
            $"blackdetect=d={FormatSeconds(minimumDuration)}:pic_th={FormatSeconds(pictureThreshold)}:pix_th={FormatSeconds(pixelThreshold)}",
            "-an",
            "-sn",
            "-f",
            "null",
            "-"
        ];
    }

    public IReadOnlyList<string> BuildFreezeDetectArguments(
        string inputPath,
        double noiseThreshold,
        double minimumDuration)
    {
        return
        [
            "-hide_banner",
            "-i",
            inputPath,
            "-map",
            "0:v:0",
            "-vf",
            $"freezedetect=n={FormatSeconds(noiseThreshold)}:d={FormatSeconds(minimumDuration)}",
            "-an",
            "-sn",
            "-f",
            "null",
            "-"
        ];
    }

    public IReadOnlyList<string> BuildVolumeAnalysisArguments(
        string inputPath,
        double windowSeconds)
    {
        var resetFrames = Math.Max((int)(windowSeconds * 25), 1);
        return
        [
            "-hide_banner",
            "-i",
            inputPath,
            "-map",
            "0:a:0",
            "-af",
            $"astats=metadata=1:reset={resetFrames},ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
            "-f",
            "null",
            "-"
        ];
    }

    private static string FormatTime(TimeSpan time)
    {
        return time.ToString(@"hh\:mm\:ss\.fff", CultureInfo.InvariantCulture);
    }

    private static string FormatSeconds(double seconds)
    {
        return seconds.ToString("0.###", CultureInfo.InvariantCulture);
    }

    private static void AppendVideoEncodingArguments(
        ICollection<string> args,
        string videoEncoder,
        string nvencPreset,
        int cq)
    {
        if (string.Equals(videoEncoder, "h264_nvenc", StringComparison.OrdinalIgnoreCase))
        {
            args.Add("-preset");
            args.Add(nvencPreset);
            args.Add("-tune");
            args.Add("hq");
            args.Add("-cq");
            args.Add(cq.ToString(CultureInfo.InvariantCulture));
            args.Add("-b:v");
            args.Add("0");
            return;
        }

        args.Add("-preset");
        args.Add("medium");
        args.Add("-crf");
        args.Add(cq.ToString(CultureInfo.InvariantCulture));
    }

    private static string BuildAtempoFilter(double speedFactor)
    {
        var remaining = speedFactor;
        var factors = new List<string>();

        while (remaining > 2.0)
        {
            factors.Add("atempo=2.0");
            remaining /= 2.0;
        }

        while (remaining < 0.5)
        {
            factors.Add("atempo=0.5");
            remaining /= 0.5;
        }

        factors.Add($"atempo={FormatSeconds(remaining)}");
        return string.Join(',', factors);
    }
}
