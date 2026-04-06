using System.Globalization;
using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class AudioCommandBuilder
{
    public IReadOnlyList<string> BuildExtractArguments(
        string inputPath,
        string outputPath,
        AudioFormat format,
        int? trackIndex,
        TimeSpan? startTime,
        TimeSpan? duration,
        bool normalize,
        int bitrateKbps = 192)
    {
        var args = new List<string> { "-y", "-hide_banner", "-nostats", "-progress", "pipe:1" };
        var effectiveFormat = GetEffectiveFormat(format, normalize);

        if (startTime.HasValue)
        {
            args.AddRange(["-ss", FormatTime(startTime.Value)]);
        }

        args.AddRange(["-i", inputPath]);

        if (duration.HasValue)
        {
            args.AddRange(["-t", duration.Value.TotalSeconds.ToString("0.000")]);
        }

        args.AddRange(["-vn", "-sn"]);

        if (trackIndex.HasValue)
        {
            args.AddRange(["-map", $"0:a:{trackIndex.Value}"]);
        }

        var filters = new List<string>();

        if (normalize)
        {
            filters.Add("loudnorm=I=-14:TP=-2:LRA=11");
        }

        switch (effectiveFormat)
        {
            case AudioFormat.Copy:
                args.AddRange(["-c:a", "copy"]);
                break;
            case AudioFormat.AAC:
                args.AddRange(["-c:a", "aac", "-profile:a", "aac_low", "-b:a", $"{bitrateKbps}k"]);
                break;
            case AudioFormat.MP3:
                args.AddRange(["-c:a", "libmp3lame", "-q:a", "2"]);
                break;
            case AudioFormat.WAV:
                args.AddRange(["-c:a", "pcm_s16le", "-ar", "44100"]);
                break;
            case AudioFormat.FLAC:
                args.AddRange(["-c:a", "flac"]);
                break;
        }

        if (filters.Count > 0 && effectiveFormat != AudioFormat.Copy)
        {
            args.AddRange(["-af", string.Join(",", filters)]);
        }

        args.Add(outputPath);
        return args;
    }

    public IReadOnlyList<string> BuildDetectSilenceArguments(
        string inputPath,
        int? trackIndex,
        double noiseThresholdDb,
        double minimumDurationSeconds)
    {
        var args = new List<string> { "-hide_banner", "-nostats" };

        args.AddRange(["-i", inputPath]);

        if (trackIndex.HasValue)
        {
            args.AddRange(["-map", $"0:a:{trackIndex.Value}"]);
        }

        args.AddRange([
            "-vn",
            "-sn",
            "-af",
            $"silencedetect=n={noiseThresholdDb.ToString("0.###", CultureInfo.InvariantCulture)}dB:d={minimumDurationSeconds.ToString("0.###", CultureInfo.InvariantCulture)}",
            "-f",
            "null",
            "-"
        ]);

        return args;
    }

    public IReadOnlyList<string> BuildMixArguments(
        string inputPath,
        string backgroundPath,
        string outputPath,
        int? trackIndex,
        TimeSpan? startTime,
        TimeSpan? duration,
        bool normalize,
        int bitrateKbps,
        double sourceVolume,
        double backgroundVolume)
    {
        var args = new List<string> { "-y", "-hide_banner", "-nostats", "-progress", "pipe:1" };

        if (startTime.HasValue)
        {
            args.AddRange(["-ss", FormatTime(startTime.Value)]);
        }

        args.AddRange(["-i", inputPath]);
        args.AddRange(["-stream_loop", "-1", "-i", backgroundPath]);
        args.AddRange(["-map_chapters", "-1"]);

        if (duration.HasValue)
        {
            args.AddRange(["-t", duration.Value.TotalSeconds.ToString("0.000", CultureInfo.InvariantCulture)]);
        }

        var mainInputLabel = trackIndex.HasValue ? $"[0:a:{trackIndex.Value}]" : "[0:a:0]";
        var mixFilters = new List<string>
        {
            $"{mainInputLabel}volume={FormatDecimal(sourceVolume)}[amain]",
            $"[1:a:0]volume={FormatDecimal(backgroundVolume)}[abgm]"
        };

        if (normalize)
        {
            mixFilters.Add("[amain][abgm]amix=inputs=2:duration=first:dropout_transition=2[amix]");
            mixFilters.Add("[amix]loudnorm=I=-14:TP=-2:LRA=11[aout]");
        }
        else
        {
            mixFilters.Add("[amain][abgm]amix=inputs=2:duration=first:dropout_transition=2[aout]");
        }

        args.AddRange([
            "-filter_complex", string.Join(';', mixFilters),
            "-map", "[aout]",
            "-vn",
            "-sn",
            "-c:a", "aac",
            "-profile:a", "aac_low",
            "-b:a", $"{bitrateKbps}k",
            "-ar", "44100",
            outputPath
        ]);

        return args;
    }

    public static AudioFormat GetEffectiveFormat(AudioFormat format, bool normalize)
    {
        return normalize && format == AudioFormat.Copy
            ? AudioFormat.AAC
            : format;
    }

    public static string GetDefaultExtension(AudioFormat format, bool normalize = false) => GetEffectiveFormat(format, normalize) switch
    {
        AudioFormat.Copy => ".mka",
        AudioFormat.AAC => ".m4a",
        AudioFormat.MP3 => ".mp3",
        AudioFormat.WAV => ".wav",
        AudioFormat.FLAC => ".flac",
        _ => ".m4a"
    };

    public static string GetDisplayName(AudioFormat format, bool normalize = false) => GetEffectiveFormat(format, normalize) switch
    {
        AudioFormat.Copy => "直拷 (原格式)",
        AudioFormat.AAC => "AAC (.m4a)",
        AudioFormat.MP3 => "MP3 (.mp3)",
        AudioFormat.WAV => "WAV (.wav)",
        AudioFormat.FLAC => "FLAC (.flac)",
        _ => format.ToString()
    };

    private static string FormatTime(TimeSpan time)
    {
        return time.ToString(@"hh\:mm\:ss\.fff");
    }

    private static string FormatDecimal(double value)
    {
        return value.ToString("0.###", CultureInfo.InvariantCulture);
    }
}
