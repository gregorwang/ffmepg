using System.Diagnostics;
using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class HardwareDetectionService
{
    public async Task<HardwareInfo> DetectAsync(CancellationToken cancellationToken = default)
    {
        var ffmpegPath = ToolPathResolver.ResolveFfmpegPath();
        var ffprobePath = ToolPathResolver.ResolveFfprobePath();
        var isNvencAvailable = false;

        try
        {
            var startInfo = new ProcessStartInfo
            {
                FileName = ffmpegPath,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            startInfo.ArgumentList.Add("-hide_banner");
            startInfo.ArgumentList.Add("-encoders");

            using var process = new Process { StartInfo = startInfo };
            process.Start();

            var stdoutTask = process.StandardOutput.ReadToEndAsync();
            var stderrTask = process.StandardError.ReadToEndAsync();

            await process.WaitForExitAsync(cancellationToken);

            var output = (await stdoutTask) + Environment.NewLine + (await stderrTask);
            isNvencAvailable = output.Contains("h264_nvenc", StringComparison.OrdinalIgnoreCase);
        }
        catch
        {
            isNvencAvailable = false;
        }

        return new HardwareInfo
        {
            IsNvencAvailable = isNvencAvailable,
            FfmpegPath = ffmpegPath,
            FfprobePath = ffprobePath
        };
    }

    public string ResolveVideoEncoder(string preferredMode, bool isNvencAvailable)
    {
        return preferredMode switch
        {
            "h264_nvenc" when isNvencAvailable => "h264_nvenc",
            "libx264" => "libx264",
            "auto" when isNvencAvailable => "h264_nvenc",
            _ => "libx264"
        };
    }
}
