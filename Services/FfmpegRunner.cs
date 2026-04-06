using System.Diagnostics;
using System.Globalization;
using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class FfmpegRunner
{
    private readonly FfmpegCommandBuilder _commandBuilder;

    public FfmpegRunner(FfmpegCommandBuilder commandBuilder)
    {
        _commandBuilder = commandBuilder;
    }

    public async Task<TranscodeResult> RunAsync(
        TranscodeJob job,
        AppSettings settings,
        string videoEncoder,
        Action<double, string> progressCallback,
        Action<string> logCallback,
        CancellationToken cancellationToken)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(job.OutputPath)!);
        var arguments = _commandBuilder.BuildArguments(job, settings, videoEncoder);

        return await RunAsync(
            arguments,
            job.SourceDurationSeconds,
            progressCallback,
            logCallback,
            cancellationToken);
    }

    public async Task<TranscodeResult> RunAsync(
        IReadOnlyList<string> arguments,
        double totalDurationSeconds,
        Action<double, string>? progressCallback,
        Action<string>? logCallback,
        CancellationToken cancellationToken)
    {
        var errorLines = new List<string>();
        var startInfo = new ProcessStartInfo
        {
            FileName = ToolPathResolver.ResolveFfmpegPath(),
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        foreach (var arg in arguments)
        {
            startInfo.ArgumentList.Add(arg);
        }

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

        var currentProgress = 0d;

        var stdoutTask = Task.Run(async () =>
        {
            while (!process.StandardOutput.EndOfStream)
            {
                var line = await process.StandardOutput.ReadLineAsync();
                if (!string.IsNullOrWhiteSpace(line))
                {
                    currentProgress = ParseProgressLine(line, totalDurationSeconds, currentProgress, progressCallback);
                }
            }
        });

        var stderrTask = Task.Run(async () =>
        {
            while (!process.StandardError.EndOfStream)
            {
                var line = await process.StandardError.ReadLineAsync();
                if (!string.IsNullOrWhiteSpace(line))
                {
                    if (errorLines.Count >= 12)
                    {
                        errorLines.RemoveAt(0);
                    }

                    errorLines.Add(line);
                    logCallback?.Invoke(line);
                }
            }
        });

        await Task.WhenAll(stdoutTask, stderrTask, process.WaitForExitAsync());

        if (cancellationToken.IsCancellationRequested)
        {
            return new TranscodeResult { Success = false, ErrorMessage = "Cancelled" };
        }

        if (process.ExitCode != 0)
        {
            return new TranscodeResult
            {
                Success = false,
                ErrorMessage = BuildErrorMessage(process.ExitCode, errorLines)
            };
        }

        progressCallback?.Invoke(100, "done");
        return new TranscodeResult { Success = true };
    }

    private static double ParseProgressLine(
        string line,
        double totalDurationSeconds,
        double currentProgress,
        Action<double, string>? progressCallback)
    {
        if (line.StartsWith("out_time_us=", StringComparison.Ordinal))
        {
            var raw = line["out_time_us=".Length..];
            if (double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out var microseconds))
            {
                return ReportProgress(microseconds / 1_000_000d, totalDurationSeconds, progressCallback);
            }

            return currentProgress;
        }

        if (line.StartsWith("out_time_ms=", StringComparison.Ordinal))
        {
            var raw = line["out_time_ms=".Length..];
            if (double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out var milliseconds))
            {
                return ReportProgress(milliseconds / 1_000d, totalDurationSeconds, progressCallback);
            }

            return currentProgress;
        }

        if (line.StartsWith("out_time=", StringComparison.Ordinal))
        {
            var raw = line["out_time=".Length..];
            if (TimeSpan.TryParse(raw, out var elapsed))
            {
                return ReportProgress(elapsed.TotalSeconds, totalDurationSeconds, progressCallback);
            }

            return currentProgress;
        }

        if (line.StartsWith("speed=", StringComparison.Ordinal))
        {
            progressCallback?.Invoke(currentProgress, line["speed=".Length..]);
        }

        return currentProgress;
    }

    private static double ReportProgress(
        double elapsedSeconds,
        double totalDurationSeconds,
        Action<double, string>? progressCallback)
    {
        if (totalDurationSeconds > 0)
        {
            var progress = Math.Clamp((elapsedSeconds / totalDurationSeconds) * 100d, 0d, 100d);
            progressCallback?.Invoke(progress, string.Empty);
            return progress;
        }

        return 0d;
    }

    private static string BuildErrorMessage(int exitCode, IReadOnlyList<string> errorLines)
    {
        var matchedLine = errorLines.LastOrDefault(line =>
            line.Contains("No space left on device", StringComparison.OrdinalIgnoreCase) ||
            line.Contains("moov atom not found", StringComparison.OrdinalIgnoreCase) ||
            line.Contains("Invalid data found when processing input", StringComparison.OrdinalIgnoreCase));

        return string.IsNullOrWhiteSpace(matchedLine)
            ? $"ffmpeg exited with code {exitCode}"
            : matchedLine;
    }
}
