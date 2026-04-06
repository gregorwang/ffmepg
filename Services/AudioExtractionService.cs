using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;
using System.Diagnostics;
using System.Globalization;
using System.Text.RegularExpressions;

namespace AnimeTranscoder.Services;

public sealed class AudioExtractionService
{
    private static readonly Regex SilenceStartRegex = new(@"silence_start:\s*(?<value>-?\d+(\.\d+)?)", RegexOptions.Compiled);
    private static readonly Regex SilenceEndRegex = new(@"silence_end:\s*(?<end>-?\d+(\.\d+)?)\s*\|\s*silence_duration:\s*(?<duration>-?\d+(\.\d+)?)", RegexOptions.Compiled);
    private readonly FfmpegRunner _runner;
    private readonly AudioCommandBuilder _commandBuilder;

    public AudioExtractionService(FfmpegRunner runner, AudioCommandBuilder commandBuilder)
    {
        _runner = runner;
        _commandBuilder = commandBuilder;
    }

    public async Task<AudioExtractionResult> ExtractAsync(
        string inputPath,
        string outputPath,
        AudioFormat format,
        int? trackIndex,
        TimeSpan? startTime,
        TimeSpan? duration,
        bool normalize,
        int bitrateKbps,
        double totalDurationSeconds,
        Action<double, string>? onProgress,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputPath))
        {
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "输入文件不存在"
            };
        }

        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrEmpty(outputDirectory) && !Directory.Exists(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        var arguments = _commandBuilder.BuildExtractArguments(
            inputPath, outputPath, format, trackIndex, startTime, duration, normalize, bitrateKbps);

        AppFileLogger.Write("AudioExtractionService", $"开始提取音频: {Path.GetFileName(inputPath)} → {Path.GetFileName(outputPath)}");
        AppFileLogger.Write("AudioExtractionService", $"ffmpeg {string.Join(' ', arguments)}");

        try
        {
            var result = await _runner.RunAsync(
                arguments,
                totalDurationSeconds,
                (progress, speed) => onProgress?.Invoke(progress, speed),
                line => AppFileLogger.Write("AudioExtraction", line),
                cancellationToken);

            if (!result.Success)
            {
                return new AudioExtractionResult
                {
                    Success = false,
                    OutputPath = outputPath,
                    ErrorMessage = result.ErrorMessage
                };
            }

            if (File.Exists(outputPath))
            {
                AppFileLogger.Write("AudioExtractionService", $"音频提取成功: {outputPath}");
                return new AudioExtractionResult
                {
                    Success = true,
                    OutputPath = outputPath
                };
            }

            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "ffmpeg 执行完毕但未生成输出文件"
            };
        }
        catch (OperationCanceledException)
        {
            AppFileLogger.Write("AudioExtractionService", "音频提取已取消。");
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "已取消"
            };
        }
        catch (Exception ex)
        {
            AppFileLogger.Write("AudioExtractionService", $"音频提取异常: {ex.Message}");
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = ex.Message
            };
        }
    }

    public async Task<IReadOnlyList<SilenceSegment>> DetectSilenceAsync(
        string inputPath,
        int? trackIndex,
        double noiseThresholdDb,
        double minimumDurationSeconds,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputPath))
        {
            throw new FileNotFoundException("输入文件不存在", inputPath);
        }

        var arguments = _commandBuilder.BuildDetectSilenceArguments(
            inputPath,
            trackIndex,
            noiseThresholdDb,
            minimumDurationSeconds);

        var startInfo = new ProcessStartInfo
        {
            FileName = ToolPathResolver.ResolveFfmpegPath(),
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        foreach (var argument in arguments)
        {
            startInfo.ArgumentList.Add(argument);
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

        double? currentSilenceStart = null;
        var segments = new List<SilenceSegment>();
        var errorLines = new List<string>();

        var stdoutTask = process.StandardOutput.ReadToEndAsync();
        var stderrTask = Task.Run(async () =>
        {
            while (!process.StandardError.EndOfStream)
            {
                var line = await process.StandardError.ReadLineAsync();
                if (string.IsNullOrWhiteSpace(line))
                {
                    continue;
                }

                AppFileLogger.Write("AudioSilenceDetect", line);
                errorLines.Add(line);
                ParseSilenceLine(line, ref currentSilenceStart, segments);
            }
        }, cancellationToken);

        await Task.WhenAll(stdoutTask, stderrTask, process.WaitForExitAsync());

        cancellationToken.ThrowIfCancellationRequested();

        if (process.ExitCode != 0)
        {
            var details = string.Join(Environment.NewLine, errorLines.TakeLast(6));
            throw new InvalidOperationException(
                string.IsNullOrWhiteSpace(details)
                    ? $"ffmpeg exited with code {process.ExitCode}"
                    : details);
        }

        return segments
            .OrderBy(segment => segment.StartSeconds)
            .ToList();
    }

    public async Task<AudioExtractionResult> MixAsync(
        string inputPath,
        string backgroundPath,
        string outputPath,
        int? trackIndex,
        TimeSpan? startTime,
        TimeSpan? duration,
        bool normalize,
        int bitrateKbps,
        double totalDurationSeconds,
        double sourceVolume,
        double backgroundVolume,
        Action<double, string>? onProgress,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputPath))
        {
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "主音频文件不存在"
            };
        }

        if (!File.Exists(backgroundPath))
        {
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "BGM 文件不存在"
            };
        }

        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrEmpty(outputDirectory) && !Directory.Exists(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        var arguments = _commandBuilder.BuildMixArguments(
            inputPath,
            backgroundPath,
            outputPath,
            trackIndex,
            startTime,
            duration,
            normalize,
            bitrateKbps,
            sourceVolume,
            backgroundVolume);

        AppFileLogger.Write("AudioMixService", $"开始混音: {Path.GetFileName(inputPath)} + {Path.GetFileName(backgroundPath)} -> {Path.GetFileName(outputPath)}");
        AppFileLogger.Write("AudioMixService", $"ffmpeg {string.Join(' ', arguments)}");

        try
        {
            var result = await _runner.RunAsync(
                arguments,
                totalDurationSeconds,
                (progress, speed) => onProgress?.Invoke(progress, speed),
                line => AppFileLogger.Write("AudioMix", line),
                cancellationToken);

            if (!result.Success)
            {
                return new AudioExtractionResult
                {
                    Success = false,
                    OutputPath = outputPath,
                    ErrorMessage = result.ErrorMessage
                };
            }

            if (File.Exists(outputPath))
            {
                AppFileLogger.Write("AudioMixService", $"音频混音成功: {outputPath}");
                return new AudioExtractionResult
                {
                    Success = true,
                    OutputPath = outputPath
                };
            }

            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "ffmpeg 执行完毕但未生成输出文件"
            };
        }
        catch (OperationCanceledException)
        {
            AppFileLogger.Write("AudioMixService", "音频混音已取消。");
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "已取消"
            };
        }
        catch (Exception ex)
        {
            AppFileLogger.Write("AudioMixService", $"音频混音异常: {ex.Message}");
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = ex.Message
            };
        }
    }

    private static void ParseSilenceLine(
        string line,
        ref double? currentSilenceStart,
        ICollection<SilenceSegment> segments)
    {
        var startMatch = SilenceStartRegex.Match(line);
        if (startMatch.Success &&
            double.TryParse(startMatch.Groups["value"].Value, NumberStyles.Float, CultureInfo.InvariantCulture, out var silenceStart))
        {
            currentSilenceStart = silenceStart;
            return;
        }

        var endMatch = SilenceEndRegex.Match(line);
        if (!endMatch.Success)
        {
            return;
        }

        if (!double.TryParse(endMatch.Groups["end"].Value, NumberStyles.Float, CultureInfo.InvariantCulture, out var silenceEnd) ||
            !double.TryParse(endMatch.Groups["duration"].Value, NumberStyles.Float, CultureInfo.InvariantCulture, out var silenceDuration))
        {
            return;
        }

        var start = currentSilenceStart ?? Math.Max(silenceEnd - silenceDuration, 0);
        currentSilenceStart = null;

        segments.Add(new SilenceSegment
        {
            StartSeconds = Math.Max(start, 0),
            EndSeconds = Math.Max(silenceEnd, 0),
            DurationSeconds = Math.Max(silenceDuration, 0)
        });
    }
}
