using System.Diagnostics;
using System.Globalization;
using System.Text.RegularExpressions;
using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class VideoClipService
{
    private static readonly Regex SceneTimeRegex = new(@"pts_time:(?<value>-?\d+(\.\d+)?)", RegexOptions.Compiled);
    private static readonly Regex BlackSegmentRegex = new(@"black_start:(?<start>-?\d+(\.\d+)?)\s+black_end:(?<end>-?\d+(\.\d+)?)\s+black_duration:(?<duration>-?\d+(\.\d+)?)", RegexOptions.Compiled);
    private static readonly Regex FreezeStartRegex = new(@"freeze_start:\s*(?<value>-?\d+(\.\d+)?)", RegexOptions.Compiled);
    private static readonly Regex FreezeEndRegex = new(@"freeze_end:\s*(?<end>-?\d+(\.\d+)?)\s*\|\s*lavfi\.freezedetect\.freeze_duration:\s*(?<duration>-?\d+(\.\d+)?)", RegexOptions.Compiled);
    private readonly FfmpegRunner _runner;
    private readonly ClipCommandBuilder _commandBuilder;

    public VideoClipService(FfmpegRunner runner, ClipCommandBuilder commandBuilder)
    {
        _runner = runner;
        _commandBuilder = commandBuilder;
    }

    public async Task<ClipResult> FastClipAsync(
        string inputPath,
        string outputPath,
        TimeSpan startTime,
        TimeSpan duration,
        Action<double, string>? onProgress,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputPath))
        {
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "输入文件不存在"
            };
        }

        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrWhiteSpace(outputDirectory) && !Directory.Exists(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        var arguments = _commandBuilder.BuildFastClipArguments(
            inputPath,
            outputPath,
            startTime,
            duration);

        AppFileLogger.Write("VideoClipService", $"开始无损快切: {Path.GetFileName(inputPath)} -> {Path.GetFileName(outputPath)}");
        AppFileLogger.Write("VideoClipService", $"ffmpeg {string.Join(' ', arguments)}");

        try
        {
            var result = await _runner.RunAsync(
                arguments,
                duration.TotalSeconds,
                (progress, speed) => onProgress?.Invoke(progress, speed),
                line => AppFileLogger.Write("VideoClip", line),
                cancellationToken);

            if (!result.Success)
            {
                return new ClipResult
                {
                    Success = false,
                    OutputPath = outputPath,
                    ErrorMessage = result.ErrorMessage
                };
            }

            if (File.Exists(outputPath))
            {
                AppFileLogger.Write("VideoClipService", $"无损快切成功: {outputPath}");
                return new ClipResult
                {
                    Success = true,
                    OutputPath = outputPath
                };
            }

            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "ffmpeg 执行完毕但未生成输出文件"
            };
        }
        catch (OperationCanceledException)
        {
            AppFileLogger.Write("VideoClipService", "无损快切已取消。");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "已取消"
            };
        }
        catch (Exception ex)
        {
            AppFileLogger.Write("VideoClipService", $"无损快切异常: {ex.Message}");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = ex.Message
            };
        }
    }

    public async Task<ClipResult> PreciseClipAsync(
        string inputPath,
        string outputPath,
        TimeSpan startTime,
        TimeSpan duration,
        string videoEncoder,
        string nvencPreset,
        int cq,
        int audioBitrateKbps,
        Action<double, string>? onProgress,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputPath))
        {
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "输入文件不存在"
            };
        }

        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrWhiteSpace(outputDirectory) && !Directory.Exists(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        var arguments = _commandBuilder.BuildPreciseClipArguments(
            inputPath,
            outputPath,
            startTime,
            duration,
            videoEncoder,
            nvencPreset,
            cq,
            audioBitrateKbps);

        AppFileLogger.Write("VideoClipService", $"开始精准裁剪: {Path.GetFileName(inputPath)} -> {Path.GetFileName(outputPath)} | encoder={videoEncoder}");
        AppFileLogger.Write("VideoClipService", $"ffmpeg {string.Join(' ', arguments)}");

        try
        {
            var result = await _runner.RunAsync(
                arguments,
                duration.TotalSeconds,
                (progress, speed) => onProgress?.Invoke(progress, speed),
                line => AppFileLogger.Write("VideoClip", line),
                cancellationToken);

            if (!result.Success)
            {
                return new ClipResult
                {
                    Success = false,
                    OutputPath = outputPath,
                    ErrorMessage = result.ErrorMessage
                };
            }

            if (File.Exists(outputPath))
            {
                AppFileLogger.Write("VideoClipService", $"精准裁剪成功: {outputPath}");
                return new ClipResult
                {
                    Success = true,
                    OutputPath = outputPath
                };
            }

            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "ffmpeg 执行完毕但未生成输出文件"
            };
        }
        catch (OperationCanceledException)
        {
            AppFileLogger.Write("VideoClipService", "精准裁剪已取消。");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "已取消"
            };
        }
        catch (Exception ex)
        {
            AppFileLogger.Write("VideoClipService", $"精准裁剪异常: {ex.Message}");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = ex.Message
            };
        }
    }

    public async Task<ClipResult> ConvertToVerticalAsync(
        string inputPath,
        string outputPath,
        VerticalMode mode,
        string videoEncoder,
        string nvencPreset,
        int cq,
        int audioBitrateKbps,
        double totalDurationSeconds,
        Action<double, string>? onProgress,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputPath))
        {
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "输入文件不存在"
            };
        }

        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrWhiteSpace(outputDirectory) && !Directory.Exists(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        var arguments = _commandBuilder.BuildVerticalAdaptArguments(
            inputPath,
            outputPath,
            mode,
            videoEncoder,
            nvencPreset,
            cq,
            audioBitrateKbps);

        AppFileLogger.Write("VideoClipService", $"开始竖屏适配: {Path.GetFileName(inputPath)} -> {Path.GetFileName(outputPath)} | mode={mode} encoder={videoEncoder}");
        AppFileLogger.Write("VideoClipService", $"ffmpeg {string.Join(' ', arguments)}");

        try
        {
            var result = await _runner.RunAsync(
                arguments,
                totalDurationSeconds,
                (progress, speed) => onProgress?.Invoke(progress, speed),
                line => AppFileLogger.Write("VideoVertical", line),
                cancellationToken);

            if (!result.Success)
            {
                return new ClipResult
                {
                    Success = false,
                    OutputPath = outputPath,
                    ErrorMessage = result.ErrorMessage
                };
            }

            if (File.Exists(outputPath))
            {
                AppFileLogger.Write("VideoClipService", $"竖屏适配成功: {outputPath}");
                return new ClipResult
                {
                    Success = true,
                    OutputPath = outputPath
                };
            }

            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "ffmpeg 执行完毕但未生成输出文件"
            };
        }
        catch (OperationCanceledException)
        {
            AppFileLogger.Write("VideoClipService", "竖屏适配已取消。");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "已取消"
            };
        }
        catch (Exception ex)
        {
            AppFileLogger.Write("VideoClipService", $"竖屏适配异常: {ex.Message}");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = ex.Message
            };
        }
    }

    public async Task<ClipResult> ConcatAsync(
        string inputPath,
        string outputPath,
        IReadOnlyList<ClipConcatSegment> segments,
        bool includeAudio,
        string videoEncoder,
        string nvencPreset,
        int cq,
        int audioBitrateKbps,
        double totalDurationSeconds,
        Action<double, string>? onProgress,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputPath))
        {
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "输入文件不存在"
            };
        }

        if (segments.Count == 0)
        {
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "至少需要一个待拼接片段"
            };
        }

        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrWhiteSpace(outputDirectory) && !Directory.Exists(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        string? filterScriptPath = null;
        var filterComplex = _commandBuilder.BuildConcatFilterComplex(segments, includeAudio);
        if (filterComplex.Length >= 7000)
        {
            var scriptDirectory = string.IsNullOrWhiteSpace(outputDirectory)
                ? Path.GetTempPath()
                : outputDirectory;
            filterScriptPath = Path.Combine(
                scriptDirectory,
                $"{Path.GetFileNameWithoutExtension(outputPath)}.concat-filter.{Guid.NewGuid():N}.txt");
            await File.WriteAllTextAsync(filterScriptPath, filterComplex, cancellationToken);
        }

        var arguments = _commandBuilder.BuildConcatArguments(
            inputPath,
            outputPath,
            segments,
            includeAudio,
            videoEncoder,
            nvencPreset,
            cq,
            audioBitrateKbps,
            filterScriptPath);

        AppFileLogger.Write("VideoClipService", $"开始片段拼接: {Path.GetFileName(inputPath)} -> {Path.GetFileName(outputPath)} | segments={segments.Count} includeAudio={includeAudio} encoder={videoEncoder}");
        AppFileLogger.Write("VideoClipService", $"ffmpeg {string.Join(' ', arguments)}");

        try
        {
            var result = await _runner.RunAsync(
                arguments,
                totalDurationSeconds,
                (progress, speed) => onProgress?.Invoke(progress, speed),
                line => AppFileLogger.Write("VideoConcat", line),
                cancellationToken);

            if (!result.Success)
            {
                return new ClipResult
                {
                    Success = false,
                    OutputPath = outputPath,
                    ErrorMessage = result.ErrorMessage
                };
            }

            if (File.Exists(outputPath))
            {
                AppFileLogger.Write("VideoClipService", $"片段拼接成功: {outputPath}");
                return new ClipResult
                {
                    Success = true,
                    OutputPath = outputPath
                };
            }

            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "ffmpeg 执行完毕但未生成输出文件"
            };
        }
        catch (OperationCanceledException)
        {
            AppFileLogger.Write("VideoClipService", "片段拼接已取消。");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "已取消"
            };
        }
        catch (Exception ex)
        {
            AppFileLogger.Write("VideoClipService", $"片段拼接异常: {ex.Message}");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = ex.Message
            };
        }
        finally
        {
            if (!string.IsNullOrWhiteSpace(filterScriptPath) && File.Exists(filterScriptPath))
            {
                try
                {
                    File.Delete(filterScriptPath);
                }
                catch
                {
                }
            }
        }
    }

    public async Task<ClipResult> GenerateGifPreviewAsync(
        string inputPath,
        string outputPath,
        TimeSpan startTime,
        TimeSpan duration,
        Action<double, string>? onProgress,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputPath))
        {
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "输入文件不存在"
            };
        }

        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrWhiteSpace(outputDirectory) && !Directory.Exists(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        var arguments = _commandBuilder.BuildGifPreviewArguments(
            inputPath,
            outputPath,
            startTime,
            duration);

        AppFileLogger.Write("VideoClipService", $"开始生成 GIF 预览: {Path.GetFileName(inputPath)} -> {Path.GetFileName(outputPath)}");
        AppFileLogger.Write("VideoClipService", $"ffmpeg {string.Join(' ', arguments)}");

        try
        {
            var result = await _runner.RunAsync(
                arguments,
                duration.TotalSeconds,
                (progress, speed) => onProgress?.Invoke(progress, speed),
                line => AppFileLogger.Write("VideoGif", line),
                cancellationToken);

            if (!result.Success)
            {
                return new ClipResult
                {
                    Success = false,
                    OutputPath = outputPath,
                    ErrorMessage = result.ErrorMessage
                };
            }

            if (File.Exists(outputPath))
            {
                AppFileLogger.Write("VideoClipService", $"GIF 预览生成成功: {outputPath}");
                return new ClipResult
                {
                    Success = true,
                    OutputPath = outputPath
                };
            }

            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "ffmpeg 执行完毕但未生成输出文件"
            };
        }
        catch (OperationCanceledException)
        {
            AppFileLogger.Write("VideoClipService", "GIF 预览生成已取消。");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "已取消"
            };
        }
        catch (Exception ex)
        {
            AppFileLogger.Write("VideoClipService", $"GIF 预览生成异常: {ex.Message}");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = ex.Message
            };
        }
    }

    public async Task<ClipResult> ChangeSpeedAsync(
        string inputPath,
        string outputPath,
        TimeSpan startTime,
        TimeSpan duration,
        double speedFactor,
        bool includeAudio,
        string videoEncoder,
        string nvencPreset,
        int cq,
        int audioBitrateKbps,
        Action<double, string>? onProgress,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputPath))
        {
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "输入文件不存在"
            };
        }

        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrWhiteSpace(outputDirectory) && !Directory.Exists(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        var arguments = _commandBuilder.BuildSpeedChangeArguments(
            inputPath,
            outputPath,
            startTime,
            duration,
            speedFactor,
            includeAudio,
            videoEncoder,
            nvencPreset,
            cq,
            audioBitrateKbps);

        AppFileLogger.Write("VideoClipService", $"开始变速处理: {Path.GetFileName(inputPath)} -> {Path.GetFileName(outputPath)} | speed={speedFactor:0.###}x encoder={videoEncoder}");
        AppFileLogger.Write("VideoClipService", $"ffmpeg {string.Join(' ', arguments)}");

        try
        {
            var result = await _runner.RunAsync(
                arguments,
                Math.Max(duration.TotalSeconds / Math.Max(speedFactor, 0.01), 0.1),
                (progress, speed) => onProgress?.Invoke(progress, speed),
                line => AppFileLogger.Write("VideoSpeed", line),
                cancellationToken);

            if (!result.Success)
            {
                return new ClipResult
                {
                    Success = false,
                    OutputPath = outputPath,
                    ErrorMessage = result.ErrorMessage
                };
            }

            if (File.Exists(outputPath))
            {
                AppFileLogger.Write("VideoClipService", $"变速处理成功: {outputPath}");
                return new ClipResult
                {
                    Success = true,
                    OutputPath = outputPath
                };
            }

            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "ffmpeg 执行完毕但未生成输出文件"
            };
        }
        catch (OperationCanceledException)
        {
            AppFileLogger.Write("VideoClipService", "变速处理已取消。");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "已取消"
            };
        }
        catch (Exception ex)
        {
            AppFileLogger.Write("VideoClipService", $"变速处理异常: {ex.Message}");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = ex.Message
            };
        }
    }

    public async Task<ClipResult> ReverseAsync(
        string inputPath,
        string outputPath,
        TimeSpan startTime,
        TimeSpan duration,
        bool includeAudio,
        string videoEncoder,
        string nvencPreset,
        int cq,
        int audioBitrateKbps,
        Action<double, string>? onProgress,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputPath))
        {
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "输入文件不存在"
            };
        }

        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrWhiteSpace(outputDirectory) && !Directory.Exists(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        var arguments = _commandBuilder.BuildReverseArguments(
            inputPath,
            outputPath,
            startTime,
            duration,
            includeAudio,
            videoEncoder,
            nvencPreset,
            cq,
            audioBitrateKbps);

        AppFileLogger.Write("VideoClipService", $"开始倒放处理: {Path.GetFileName(inputPath)} -> {Path.GetFileName(outputPath)} | encoder={videoEncoder}");
        AppFileLogger.Write("VideoClipService", $"ffmpeg {string.Join(' ', arguments)}");

        try
        {
            var result = await _runner.RunAsync(
                arguments,
                Math.Max(duration.TotalSeconds, 0.1),
                (progress, speed) => onProgress?.Invoke(progress, speed),
                line => AppFileLogger.Write("VideoReverse", line),
                cancellationToken);

            if (!result.Success)
            {
                return new ClipResult
                {
                    Success = false,
                    OutputPath = outputPath,
                    ErrorMessage = result.ErrorMessage
                };
            }

            if (File.Exists(outputPath))
            {
                AppFileLogger.Write("VideoClipService", $"倒放处理成功: {outputPath}");
                return new ClipResult
                {
                    Success = true,
                    OutputPath = outputPath
                };
            }

            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "ffmpeg 执行完毕但未生成输出文件"
            };
        }
        catch (OperationCanceledException)
        {
            AppFileLogger.Write("VideoClipService", "倒放处理已取消。");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "已取消"
            };
        }
        catch (Exception ex)
        {
            AppFileLogger.Write("VideoClipService", $"倒放处理异常: {ex.Message}");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = ex.Message
            };
        }
    }

    public async Task<ClipResult> AddPictureInPictureAsync(
        string inputPath,
        string overlayPath,
        string outputPath,
        PipCorner corner,
        double overlayScale,
        string videoEncoder,
        string nvencPreset,
        int cq,
        int audioBitrateKbps,
        double totalDurationSeconds,
        Action<double, string>? onProgress,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputPath))
        {
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "主视频文件不存在"
            };
        }

        if (!File.Exists(overlayPath))
        {
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "画中画素材不存在"
            };
        }

        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrWhiteSpace(outputDirectory) && !Directory.Exists(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        var arguments = _commandBuilder.BuildPictureInPictureArguments(
            inputPath,
            overlayPath,
            outputPath,
            corner,
            overlayScale,
            videoEncoder,
            nvencPreset,
            cq,
            audioBitrateKbps);

        AppFileLogger.Write("VideoClipService", $"开始画中画合成: {Path.GetFileName(inputPath)} + {Path.GetFileName(overlayPath)} -> {Path.GetFileName(outputPath)} | corner={corner} scale={overlayScale:0.###}");
        AppFileLogger.Write("VideoClipService", $"ffmpeg {string.Join(' ', arguments)}");

        try
        {
            var result = await _runner.RunAsync(
                arguments,
                totalDurationSeconds,
                (progress, speed) => onProgress?.Invoke(progress, speed),
                line => AppFileLogger.Write("VideoPip", line),
                cancellationToken);

            if (!result.Success)
            {
                return new ClipResult
                {
                    Success = false,
                    OutputPath = outputPath,
                    ErrorMessage = result.ErrorMessage
                };
            }

            if (File.Exists(outputPath))
            {
                AppFileLogger.Write("VideoClipService", $"画中画合成成功: {outputPath}");
                return new ClipResult
                {
                    Success = true,
                    OutputPath = outputPath
                };
            }

            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "ffmpeg 执行完毕但未生成输出文件"
            };
        }
        catch (OperationCanceledException)
        {
            AppFileLogger.Write("VideoClipService", "画中画合成已取消。");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "已取消"
            };
        }
        catch (Exception ex)
        {
            AppFileLogger.Write("VideoClipService", $"画中画合成异常: {ex.Message}");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = ex.Message
            };
        }
    }

    public async Task<IReadOnlyList<SceneCutPoint>> DetectScenesAsync(
        string inputPath,
        double threshold,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputPath))
        {
            throw new FileNotFoundException("输入文件不存在", inputPath);
        }

        var arguments = _commandBuilder.BuildSceneDetectArguments(inputPath, threshold);
        var cuts = new List<SceneCutPoint>();
        await RunAnalysisAsync(
            arguments,
            "VideoSceneDetect",
            line => ParseSceneLine(line, cuts),
            "场景检测",
            cancellationToken);

        return cuts
            .GroupBy(point => Math.Round(point.TimeSeconds, 3))
            .Select(group => new SceneCutPoint
            {
                Sequence = 0,
                TimeSeconds = group.First().TimeSeconds
            })
            .OrderBy(point => point.TimeSeconds)
            .Select((point, index) => new SceneCutPoint
            {
                Sequence = index + 1,
                TimeSeconds = point.TimeSeconds
            })
            .ToList();
    }

    public async Task<IReadOnlyList<VideoAnalysisSegment>> DetectBlackSegmentsAsync(
        string inputPath,
        double pictureThreshold,
        double pixelThreshold,
        double minimumDuration,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputPath))
        {
            throw new FileNotFoundException("输入文件不存在", inputPath);
        }

        var arguments = _commandBuilder.BuildBlackDetectArguments(inputPath, pictureThreshold, pixelThreshold, minimumDuration);
        var segments = new List<VideoAnalysisSegment>();
        await RunAnalysisAsync(
            arguments,
            "VideoBlackDetect",
            line => ParseBlackSegmentLine(line, segments),
            "黑场检测",
            cancellationToken);

        return segments
            .OrderBy(segment => segment.StartSeconds)
            .ToList();
    }

    public async Task<IReadOnlyList<VideoAnalysisSegment>> DetectFreezeSegmentsAsync(
        string inputPath,
        double noiseThreshold,
        double minimumDuration,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputPath))
        {
            throw new FileNotFoundException("输入文件不存在", inputPath);
        }

        var arguments = _commandBuilder.BuildFreezeDetectArguments(inputPath, noiseThreshold, minimumDuration);
        var segments = new List<VideoAnalysisSegment>();
        double? currentFreezeStart = null;

        await RunAnalysisAsync(
            arguments,
            "VideoFreezeDetect",
            line => ParseFreezeSegmentLine(line, ref currentFreezeStart, segments),
            "冻帧检测",
            cancellationToken);

        return segments
            .OrderBy(segment => segment.StartSeconds)
            .ToList();
    }

    private async Task RunAnalysisAsync(
        IReadOnlyList<string> arguments,
        string logCategory,
        Action<string> parseLine,
        string analysisName,
        CancellationToken cancellationToken)
    {
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

                AppFileLogger.Write(logCategory, line);
                parseLine(line);
            }
        }, cancellationToken);

        await Task.WhenAll(stdoutTask, stderrTask, process.WaitForExitAsync());

        cancellationToken.ThrowIfCancellationRequested();

        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException($"ffmpeg {analysisName}失败，退出码 {process.ExitCode}");
        }
    }

    private static void ParseSceneLine(string line, ICollection<SceneCutPoint> cuts)
    {
        var match = SceneTimeRegex.Match(line);
        if (!match.Success ||
            !double.TryParse(match.Groups["value"].Value, NumberStyles.Float, CultureInfo.InvariantCulture, out var timeSeconds))
        {
            return;
        }

        cuts.Add(new SceneCutPoint
        {
            TimeSeconds = Math.Max(timeSeconds, 0)
        });
    }

    private static void ParseBlackSegmentLine(string line, ICollection<VideoAnalysisSegment> segments)
    {
        var match = BlackSegmentRegex.Match(line);
        if (!match.Success ||
            !double.TryParse(match.Groups["start"].Value, NumberStyles.Float, CultureInfo.InvariantCulture, out var start) ||
            !double.TryParse(match.Groups["end"].Value, NumberStyles.Float, CultureInfo.InvariantCulture, out var end) ||
            !double.TryParse(match.Groups["duration"].Value, NumberStyles.Float, CultureInfo.InvariantCulture, out var duration))
        {
            return;
        }

        segments.Add(new VideoAnalysisSegment
        {
            Kind = "黑场",
            StartSeconds = Math.Max(start, 0),
            EndSeconds = Math.Max(end, 0),
            DurationSeconds = Math.Max(duration, 0)
        });
    }

    private static void ParseFreezeSegmentLine(string line, ref double? currentFreezeStart, ICollection<VideoAnalysisSegment> segments)
    {
        var startMatch = FreezeStartRegex.Match(line);
        if (startMatch.Success &&
            double.TryParse(startMatch.Groups["value"].Value, NumberStyles.Float, CultureInfo.InvariantCulture, out var freezeStart))
        {
            currentFreezeStart = freezeStart;
            return;
        }

        var endMatch = FreezeEndRegex.Match(line);
        if (!endMatch.Success ||
            !double.TryParse(endMatch.Groups["end"].Value, NumberStyles.Float, CultureInfo.InvariantCulture, out var freezeEnd) ||
            !double.TryParse(endMatch.Groups["duration"].Value, NumberStyles.Float, CultureInfo.InvariantCulture, out var freezeDuration))
        {
            return;
        }

        var start = currentFreezeStart ?? Math.Max(freezeEnd - freezeDuration, 0);
        currentFreezeStart = null;

        segments.Add(new VideoAnalysisSegment
        {
            Kind = "冻帧",
            StartSeconds = Math.Max(start, 0),
            EndSeconds = Math.Max(freezeEnd, 0),
            DurationSeconds = Math.Max(freezeDuration, 0)
        });
    }

    private static readonly Regex VolumeTimeRegex = new(@"pts_time:(?\u003ctime\u003e-?\d+(\.\d+)?)", RegexOptions.Compiled);
    private static readonly Regex VolumeLevelRegex = new(@"lavfi\.astats\.Overall\.RMS_level=(?<level>-?\d+(\.\d+)?|-inf)", RegexOptions.Compiled);

    public async Task<IReadOnlyList<VolumeSegment>> DetectVolumeSegmentsAsync(
        string inputPath,
        double windowSeconds,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputPath))
        {
            throw new FileNotFoundException("输入文件不存在", inputPath);
        }

        var arguments = _commandBuilder.BuildVolumeAnalysisArguments(inputPath, windowSeconds);

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

        var samples = new List<(double Time, double Level)>();
        double? pendingTime = null;

        var stdoutTask = Task.Run(async () =>
        {
            while (!process.StandardOutput.EndOfStream)
            {
                var line = await process.StandardOutput.ReadLineAsync();
                if (string.IsNullOrWhiteSpace(line))
                {
                    continue;
                }

                var timeMatch = VolumeTimeRegex.Match(line);
                if (timeMatch.Success &&
                    double.TryParse(timeMatch.Groups["time"].Value, NumberStyles.Float, CultureInfo.InvariantCulture, out var time))
                {
                    pendingTime = time;
                    continue;
                }

                var levelMatch = VolumeLevelRegex.Match(line);
                if (levelMatch.Success && pendingTime.HasValue)
                {
                    var levelText = levelMatch.Groups["level"].Value;
                    var level = string.Equals(levelText, "-inf", StringComparison.OrdinalIgnoreCase)
                        ? double.NegativeInfinity
                        : double.TryParse(levelText, NumberStyles.Float, CultureInfo.InvariantCulture, out var parsed)
                            ? parsed
                            : double.NegativeInfinity;

                    samples.Add((pendingTime.Value, level));
                    pendingTime = null;
                }
            }
        }, cancellationToken);

        var stderrTask = Task.Run(async () =>
        {
            while (!process.StandardError.EndOfStream)
            {
                var line = await process.StandardError.ReadLineAsync();
                if (!string.IsNullOrWhiteSpace(line))
                {
                    AppFileLogger.Write("VolumeAnalysis", line);
                }
            }
        }, cancellationToken);

        await Task.WhenAll(stdoutTask, stderrTask, process.WaitForExitAsync());

        cancellationToken.ThrowIfCancellationRequested();

        if (samples.Count == 0)
        {
            AppFileLogger.Write("VolumeAnalysis", "未获取到音量数据，可能没有音轨。");
            return [];
        }

        var segments = new List<VolumeSegment>();
        var windowStart = 0d;

        while (windowStart < samples[^1].Time)
        {
            var windowEnd = windowStart + windowSeconds;
            var windowSamples = samples
                .Where(s => s.Time >= windowStart && s.Time < windowEnd)
                .Select(s => s.Level)
                .Where(l => !double.IsNegativeInfinity(l))
                .ToList();

            var meanDb = windowSamples.Count > 0
                ? windowSamples.Average()
                : double.NegativeInfinity;
            var peakDb = windowSamples.Count > 0
                ? windowSamples.Max()
                : double.NegativeInfinity;

            segments.Add(new VolumeSegment
            {
                StartSeconds = windowStart,
                EndSeconds = windowEnd,
                MeanVolumeDb = meanDb,
                PeakVolumeDb = peakDb
            });

            windowStart = windowEnd;
        }

        AppFileLogger.Write("VolumeAnalysis", $"音量分析完成：{segments.Count} 个窗口，采样点 {samples.Count}");
        return segments;
    }
}
