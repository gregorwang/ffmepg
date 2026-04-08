using System.Diagnostics;
using System.Globalization;
using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class OverlayFramePreviewService
{
    private readonly FfmpegCommandBuilder _commandBuilder;

    public OverlayFramePreviewService(FfmpegCommandBuilder commandBuilder)
    {
        _commandBuilder = commandBuilder;
    }

    public async Task<FramePreviewResult> GenerateAsync(
        string inputPath,
        double previewTimeSeconds,
        int? subtitleStreamOrdinal,
        string? assPath,
        CancellationToken cancellationToken = default)
    {
        var previewDirectory = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "AnimeTranscoder",
            "preview");
        Directory.CreateDirectory(previewDirectory);

        var outputPath = Path.Combine(
            previewDirectory,
            $"{Path.GetFileNameWithoutExtension(inputPath)}-{DateTime.UtcNow:yyyyMMddHHmmssfff}.png");

        var startInfo = new ProcessStartInfo
        {
            FileName = ToolPathResolver.ResolveFfmpegPath(),
            RedirectStandardError = true,
            RedirectStandardOutput = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        startInfo.ArgumentList.Add("-y");
        startInfo.ArgumentList.Add("-hide_banner");
        startInfo.ArgumentList.Add("-loglevel");
        startInfo.ArgumentList.Add("error");
        startInfo.ArgumentList.Add("-i");
        startInfo.ArgumentList.Add(inputPath);
        startInfo.ArgumentList.Add("-ss");
        startInfo.ArgumentList.Add(previewTimeSeconds.ToString("0.###", CultureInfo.InvariantCulture));

        var videoFilter = _commandBuilder.BuildVideoFilter(inputPath, subtitleStreamOrdinal, assPath);
        if (!string.IsNullOrWhiteSpace(videoFilter))
        {
            startInfo.ArgumentList.Add("-vf");
            startInfo.ArgumentList.Add(videoFilter);
        }

        startInfo.ArgumentList.Add("-frames:v");
        startInfo.ArgumentList.Add("1");
        startInfo.ArgumentList.Add(outputPath);

        using var process = new Process { StartInfo = startInfo };
        process.Start();

        using var registration = cancellationToken.Register(() =>
        {
            try
            {
                if (!process.HasExited)
                {
                    process.Kill(entireProcessTree: true);
                }
            }
            catch
            {
            }
        });

        var stderr = await process.StandardError.ReadToEndAsync(cancellationToken);
        await process.WaitForExitAsync(cancellationToken);

        if (cancellationToken.IsCancellationRequested)
        {
            return new FramePreviewResult
            {
                Success = false,
                Message = "预览已取消"
            };
        }

        if (process.ExitCode != 0 || !File.Exists(outputPath))
        {
            return new FramePreviewResult
            {
                Success = false,
                Message = string.IsNullOrWhiteSpace(stderr) ? $"ffmpeg exited with code {process.ExitCode}" : stderr.Trim()
            };
        }

        return new FramePreviewResult
        {
            Success = true,
            OutputPath = outputPath,
            Message = $"预览帧已生成：{Path.GetFileName(outputPath)}"
        };
    }
}
