using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class FfprobeService
{
    public async Task<MediaProbeResult?> ProbeAsync(string mediaPath, CancellationToken cancellationToken = default)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = ToolPathResolver.ResolveFfprobePath(),
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        startInfo.ArgumentList.Add("-v");
        startInfo.ArgumentList.Add("error");
        startInfo.ArgumentList.Add("-show_streams");
        startInfo.ArgumentList.Add("-show_format");
        startInfo.ArgumentList.Add("-of");
        startInfo.ArgumentList.Add("json");
        startInfo.ArgumentList.Add(mediaPath);

        using var process = new Process { StartInfo = startInfo };
        process.Start();

        var outputTask = process.StandardOutput.ReadToEndAsync();
        var errorTask = process.StandardError.ReadToEndAsync();

        await process.WaitForExitAsync(cancellationToken);

        var output = await outputTask;
        var error = await errorTask;

        if (process.ExitCode != 0 || string.IsNullOrWhiteSpace(output))
        {
            throw new InvalidOperationException($"ffprobe failed for {mediaPath}: {error}");
        }

        using var json = JsonDocument.Parse(output);
        var root = json.RootElement;

        return new MediaProbeResult
        {
            Path = mediaPath,
            FileSizeBytes = ReadFileSize(root),
            Duration = ReadDuration(root),
            AudioTracks = ReadAudioTracks(root),
            SubtitleTracks = ReadSubtitleTracks(root),
            AnalysisSource = "ffprobe",
            Message = "已通过 ffprobe 完成媒体探测"
        };
    }

    private static long ReadFileSize(JsonElement root)
    {
        if (root.TryGetProperty("format", out var format) &&
            format.TryGetProperty("size", out var sizeElement) &&
            long.TryParse(sizeElement.GetString(), NumberStyles.Integer, CultureInfo.InvariantCulture, out var size))
        {
            return size;
        }

        return 0;
    }

    private static TimeSpan ReadDuration(JsonElement root)
    {
        if (root.TryGetProperty("format", out var format) &&
            format.TryGetProperty("duration", out var durationElement) &&
            double.TryParse(durationElement.GetString(), NumberStyles.Float, CultureInfo.InvariantCulture, out var seconds))
        {
            return TimeSpan.FromSeconds(seconds);
        }

        return TimeSpan.Zero;
    }

    private static List<SubtitleTrackInfo> ReadSubtitleTracks(JsonElement root)
    {
        var results = new List<SubtitleTrackInfo>();

        if (!root.TryGetProperty("streams", out var streams))
        {
            return results;
        }

        foreach (var stream in streams.EnumerateArray())
        {
            if (!stream.TryGetProperty("codec_type", out var codecType) ||
                !string.Equals(codecType.GetString(), "subtitle", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var index = stream.TryGetProperty("index", out var indexElement) ? indexElement.GetInt32() : -1;
            var title = string.Empty;
            var language = string.Empty;
            var isDefault = false;
            var codecName = stream.TryGetProperty("codec_name", out var codecNameElement)
                ? codecNameElement.GetString() ?? string.Empty
                : string.Empty;

            if (stream.TryGetProperty("tags", out var tags))
            {
                if (tags.TryGetProperty("title", out var titleElement))
                {
                    title = titleElement.GetString() ?? string.Empty;
                }

                if (tags.TryGetProperty("language", out var languageElement))
                {
                    language = languageElement.GetString() ?? string.Empty;
                }
            }

            if (stream.TryGetProperty("disposition", out var disposition) &&
                disposition.TryGetProperty("default", out var defaultElement))
            {
                isDefault = defaultElement.GetInt32() == 1;
            }

            results.Add(new SubtitleTrackInfo
            {
                Index = index,
                Title = title,
                Language = language,
                IsDefault = isDefault,
                CodecName = codecName,
                AnalysisSource = "ffprobe"
            });
        }

        return results;
    }

    private static List<AudioTrackInfo> ReadAudioTracks(JsonElement root)
    {
        var results = new List<AudioTrackInfo>();
        var audioTrackIndex = 0;

        if (!root.TryGetProperty("streams", out var streams))
        {
            return results;
        }

        foreach (var stream in streams.EnumerateArray())
        {
            if (!stream.TryGetProperty("codec_type", out var codecType) ||
                !string.Equals(codecType.GetString(), "audio", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var index = stream.TryGetProperty("index", out var indexElement) ? indexElement.GetInt32() : -1;
            var codecName = stream.TryGetProperty("codec_name", out var codecNameElement)
                ? codecNameElement.GetString() ?? string.Empty
                : string.Empty;
            var channels = stream.TryGetProperty("channels", out var channelsElement) ? channelsElement.GetInt32() : 0;
            var channelLayout = stream.TryGetProperty("channel_layout", out var channelLayoutElement)
                ? channelLayoutElement.GetString() ?? string.Empty
                : string.Empty;
            var sampleRateText = stream.TryGetProperty("sample_rate", out var sampleRateElement)
                ? sampleRateElement.GetString() ?? "0"
                : "0";
            int.TryParse(sampleRateText, out var sampleRate);
            var bitRateText = stream.TryGetProperty("bit_rate", out var bitRateElement)
                ? bitRateElement.GetString() ?? "0"
                : "0";
            long.TryParse(bitRateText, out var bitRate);

            var title = string.Empty;
            var language = string.Empty;
            var isDefault = false;

            if (stream.TryGetProperty("tags", out var tags))
            {
                if (tags.TryGetProperty("title", out var titleElement))
                {
                    title = titleElement.GetString() ?? string.Empty;
                }

                if (tags.TryGetProperty("language", out var languageElement))
                {
                    language = languageElement.GetString() ?? string.Empty;
                }
            }

            if (stream.TryGetProperty("disposition", out var disposition) &&
                disposition.TryGetProperty("default", out var defaultElement))
            {
                isDefault = defaultElement.GetInt32() == 1;
            }

            results.Add(new AudioTrackInfo
            {
                Index = audioTrackIndex++,
                StreamIndex = index,
                CodecName = codecName,
                Language = language,
                Title = title,
                Channels = channels,
                ChannelLayout = channelLayout,
                SampleRate = sampleRate,
                BitRate = bitRate,
                IsDefault = isDefault
            });
        }

        return results;
    }
}
