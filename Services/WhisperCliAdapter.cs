using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class WhisperCliAdapter : ITranscriptionService
{
    private static readonly Regex ProgressRegex = new(@"(?<value>\d+(?:\.\d+)?)\s*%", RegexOptions.Compiled);
    private readonly AudioExtractionService _audioExtractionService;

    public WhisperCliAdapter(AudioExtractionService audioExtractionService)
    {
        _audioExtractionService = audioExtractionService;
    }

    public async Task<TranscriptDocument> TranscribeAsync(
        string audioFilePath,
        WhisperOptions options,
        IProgress<double>? progress,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(audioFilePath))
        {
            throw new ArgumentException("音频文件路径不能为空。", nameof(audioFilePath));
        }

        var absoluteAudioPath = Path.GetFullPath(audioFilePath);
        if (!File.Exists(absoluteAudioPath))
        {
            throw new FileNotFoundException("音频文件不存在。", absoluteAudioPath);
        }

        var executablePath = ResolveExecutablePath(options.ExecutablePath);
        if (string.IsNullOrWhiteSpace(executablePath))
        {
            throw new FileNotFoundException("Whisper 可执行文件不存在，且未在 PATH 中找到。", options.ExecutablePath);
        }

        var modelPath = Path.GetFullPath(options.ModelPath);
        if (!File.Exists(modelPath))
        {
            throw new FileNotFoundException("Whisper 模型文件不存在。", modelPath);
        }

        string? preparedInputPath = null;
        string? outputJsonPath = null;

        try
        {
            preparedInputPath = await PrepareInputAsync(absoluteAudioPath, cancellationToken);
            outputJsonPath = $"{preparedInputPath}.json";

            if (File.Exists(outputJsonPath))
            {
                File.Delete(outputJsonPath);
            }

            var startInfo = new ProcessStartInfo
            {
                FileName = executablePath,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            foreach (var argument in BuildArguments(preparedInputPath, modelPath, options))
            {
                startInfo.ArgumentList.Add(argument);
            }

            var stderrLines = new List<string>();
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
                catch (Exception ex)
                {
                    AppFileLogger.Write("WhisperCliAdapter", $"取消 whisper 进程失败：{ex.Message}");
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

                    if (stderrLines.Count >= 24)
                    {
                        stderrLines.RemoveAt(0);
                    }

                    stderrLines.Add(line);
                    AppFileLogger.Write("WhisperCliAdapter", line);
                    ReportProgress(progress, line);
                }
            }, cancellationToken);

            await Task.WhenAll(stdoutTask, stderrTask, process.WaitForExitAsync(cancellationToken));
            cancellationToken.ThrowIfCancellationRequested();

            if (process.ExitCode != 0)
            {
                throw new InvalidOperationException(BuildProcessErrorMessage(process.ExitCode, stderrLines));
            }

            if (!File.Exists(outputJsonPath))
            {
                throw new InvalidOperationException("Whisper 未生成 JSON 输出文件。");
            }

            var json = await File.ReadAllTextAsync(outputJsonPath, cancellationToken);
            return ParseTranscriptDocument(absoluteAudioPath, json);
        }
        finally
        {
            TryDeleteFile(outputJsonPath);

            if (!string.Equals(preparedInputPath, absoluteAudioPath, StringComparison.OrdinalIgnoreCase))
            {
                TryDeleteFile(preparedInputPath);
            }
        }
    }

    private async Task<string> PrepareInputAsync(string audioFilePath, CancellationToken cancellationToken)
    {
        if (IsWaveFile(audioFilePath))
        {
            return audioFilePath;
        }

        var tempPath = Path.Combine(Path.GetTempPath(), $"AnimeTranscoder.Whisper.{Guid.NewGuid():N}.wav");
        var result = await _audioExtractionService.ExtractWorkAudioAsync(
            audioFilePath,
            tempPath,
            trackIndex: null,
            sampleRate: 16000,
            onProgress: null,
            cancellationToken);

        if (!result.Success)
        {
            TryDeleteFile(tempPath);
            throw new InvalidOperationException(result.ErrorMessage ?? "Whisper 输入音频转换失败。");
        }

        return tempPath;
    }

    private static TranscriptDocument ParseTranscriptDocument(string audioFilePath, string json)
    {
        WhisperOutputPayload? payload;
        try
        {
            payload = JsonSerializer.Deserialize<WhisperOutputPayload>(json, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });
        }
        catch (JsonException ex)
        {
            throw new InvalidOperationException("Whisper 输出 JSON 解析失败。", ex);
        }

        var segments = payload?.Transcription?
            .Select((item, index) => new TranscriptSegment
            {
                Id = $"seg_{index + 1:000}",
                Start = (item.Offsets?.From ?? 0) / 1000d,
                End = (item.Offsets?.To ?? 0) / 1000d,
                Text = item.Text?.Trim() ?? string.Empty,
                Source = "whisper.cpp",
                Channel = "mono"
            })
            .ToList() ?? [];

        return new TranscriptDocument
        {
            AudioPath = audioFilePath,
            Segments = segments
        };
    }

    private static IReadOnlyList<string> BuildArguments(string inputWavPath, string modelPath, WhisperOptions options)
    {
        var arguments = new List<string>
        {
            "-m",
            modelPath,
            "-f",
            inputWavPath,
            "-oj",
            "-l",
            string.IsNullOrWhiteSpace(options.Language) ? "auto" : options.Language
        };

        if (options.Threads > 0)
        {
            arguments.Add("-t");
            arguments.Add(options.Threads.ToString(CultureInfo.InvariantCulture));
        }

        arguments.AddRange(SplitExtraArguments(options.ExtraArgs));
        return arguments;
    }

    private static IEnumerable<string> SplitExtraArguments(string extraArgs)
    {
        if (string.IsNullOrWhiteSpace(extraArgs))
        {
            yield break;
        }

        var current = new StringBuilder();
        var inQuotes = false;

        foreach (var ch in extraArgs)
        {
            if (ch == '"')
            {
                inQuotes = !inQuotes;
                continue;
            }

            if (char.IsWhiteSpace(ch) && !inQuotes)
            {
                if (current.Length > 0)
                {
                    yield return current.ToString();
                    current.Clear();
                }

                continue;
            }

            current.Append(ch);
        }

        if (current.Length > 0)
        {
            yield return current.ToString();
        }
    }

    private static string? ResolveExecutablePath(string executablePath)
    {
        if (string.IsNullOrWhiteSpace(executablePath))
        {
            return null;
        }

        if (executablePath.Contains(Path.DirectorySeparatorChar) ||
            executablePath.Contains(Path.AltDirectorySeparatorChar))
        {
            var absolutePath = Path.GetFullPath(executablePath);
            return File.Exists(absolutePath) ? absolutePath : null;
        }

        var pathValue = Environment.GetEnvironmentVariable("PATH");
        if (string.IsNullOrWhiteSpace(pathValue))
        {
            return null;
        }

        var candidateNames = BuildExecutableCandidates(executablePath);
        foreach (var directory in pathValue.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            foreach (var candidateName in candidateNames)
            {
                var candidatePath = Path.Combine(directory, candidateName);
                if (File.Exists(candidatePath))
                {
                    return candidatePath;
                }
            }
        }

        return null;
    }

    private static IEnumerable<string> BuildExecutableCandidates(string executablePath)
    {
        if (Path.HasExtension(executablePath))
        {
            yield return executablePath;
            yield break;
        }

        yield return executablePath;

        var pathext = Environment.GetEnvironmentVariable("PATHEXT");
        var extensions = string.IsNullOrWhiteSpace(pathext)
            ? [".exe", ".cmd", ".bat"]
            : pathext.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

        foreach (var extension in extensions)
        {
            yield return executablePath + extension;
        }
    }

    private static bool IsWaveFile(string path)
    {
        if (!string.Equals(Path.GetExtension(path), ".wav", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        try
        {
            using var stream = File.OpenRead(path);
            if (stream.Length < 12)
            {
                return false;
            }

            Span<byte> header = stackalloc byte[12];
            _ = stream.Read(header);

            return Encoding.ASCII.GetString(header[..4]) == "RIFF" &&
                   Encoding.ASCII.GetString(header.Slice(8, 4)) == "WAVE";
        }
        catch (Exception ex)
        {
            AppFileLogger.Write("WhisperCliAdapter", $"读取 WAV 头失败：{ex.Message}");
            return false;
        }
    }

    private static void ReportProgress(IProgress<double>? progress, string line)
    {
        if (progress is null)
        {
            return;
        }

        var match = ProgressRegex.Match(line);
        if (!match.Success)
        {
            return;
        }

        if (double.TryParse(match.Groups["value"].Value, NumberStyles.Float, CultureInfo.InvariantCulture, out var value))
        {
            progress.Report(value);
        }
    }

    private static string BuildProcessErrorMessage(int exitCode, IReadOnlyList<string> stderrLines)
    {
        var details = string.Join(Environment.NewLine, stderrLines.TakeLast(8));
        return string.IsNullOrWhiteSpace(details)
            ? $"whisper exited with code {exitCode}"
            : details;
    }

    private static void TryDeleteFile(string? path)
    {
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
        {
            return;
        }

        try
        {
            File.Delete(path);
        }
        catch (Exception ex)
        {
            AppFileLogger.Write("WhisperCliAdapter", $"清理临时文件失败：{path} | {ex.Message}");
        }
    }

    private sealed class WhisperOutputPayload
    {
        public List<WhisperSegmentPayload> Transcription { get; set; } = [];
    }

    private sealed class WhisperSegmentPayload
    {
        public WhisperOffsetsPayload? Offsets { get; set; }
        public string? Text { get; set; }
    }

    private sealed class WhisperOffsetsPayload
    {
        public int From { get; set; }
        public int To { get; set; }
    }
}
