using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class DouyinExportService
{
    private readonly FfmpegRunner _runner;
    private readonly DouyinCommandBuilder _commandBuilder;

    public DouyinExportService(FfmpegRunner runner, DouyinCommandBuilder commandBuilder)
    {
        _runner = runner;
        _commandBuilder = commandBuilder;
    }

    public async Task<ClipResult> ExportAsync(
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

        if (!sourceHasAudio && (string.IsNullOrWhiteSpace(bgmPath) || !File.Exists(bgmPath)))
        {
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "源文件没有音轨，且未提供可用 BGM"
            };
        }

        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrWhiteSpace(outputDirectory) && !Directory.Exists(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        var arguments = _commandBuilder.BuildExportArguments(
            inputPath,
            outputPath,
            bgmPath,
            preset,
            subtitleStreamOrdinal,
            titleText,
            watermarkText,
            sourceVolume,
            bgmVolume,
            sourceHasAudio,
            totalDurationSeconds,
            videoEncoder,
            nvencPreset,
            cq,
            audioBitrateKbps);

        AppFileLogger.Write("DouyinExportService", $"开始抖音直出: {Path.GetFileName(inputPath)} -> {Path.GetFileName(outputPath)} | preset={preset} encoder={videoEncoder}");
        AppFileLogger.Write("DouyinExportService", $"ffmpeg {string.Join(' ', arguments)}");

        try
        {
            var result = await _runner.RunAsync(
                arguments,
                totalDurationSeconds,
                (progress, speed) => onProgress?.Invoke(progress, speed),
                line => AppFileLogger.Write("DouyinExport", line),
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
                AppFileLogger.Write("DouyinExportService", $"抖音直出成功: {outputPath}");
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
            AppFileLogger.Write("DouyinExportService", "抖音直出已取消。");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "已取消"
            };
        }
        catch (Exception ex)
        {
            AppFileLogger.Write("DouyinExportService", $"抖音直出异常: {ex.Message}");
            return new ClipResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = ex.Message
            };
        }
    }
}
