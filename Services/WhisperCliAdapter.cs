using System.Diagnostics;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class WhisperCliAdapter : ITranscriptionService
{
    private static readonly Regex ProgressRegex = new(@"(?<value>\d+(?:\.\d+)?)\s*%", RegexOptions.Compiled);
    private static readonly JsonSerializerOptions CacheJsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    };
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

        try
        {
            preparedInputPath = await PrepareInputAsync(absoluteAudioPath, cancellationToken);
            var durationSeconds = ReadWaveDurationSeconds(preparedInputPath);
            if (ShouldChunk(durationSeconds, options))
            {
                return await TranscribeChunkedAsync(
                    absoluteAudioPath,
                    preparedInputPath,
                    executablePath,
                    modelPath,
                    options,
                    durationSeconds,
                    progress,
                    cancellationToken);
            }

            var json = await ExecuteWhisperAsync(
                preparedInputPath,
                executablePath,
                modelPath,
                options,
                startOffsetSeconds: 0d,
                progress,
                cancellationToken);

            return ParseTranscriptDocument(
                absoluteAudioPath,
                json,
                filterStartSeconds: null,
                filterEndSeconds: null,
                isLastChunk: true);
        }
        finally
        {
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

    private async Task<TranscriptDocument> TranscribeChunkedAsync(
        string audioFilePath,
        string preparedInputPath,
        string executablePath,
        string modelPath,
        WhisperOptions options,
        double durationSeconds,
        IProgress<double>? progress,
        CancellationToken cancellationToken)
    {
        var chunkPlans = BuildChunkPlans(durationSeconds, options);
        var cacheDirectory = BuildChunkCacheDirectory(audioFilePath, options);
        Directory.CreateDirectory(cacheDirectory);

        var mergedSegments = new List<TranscriptSegment>();
        var totalCoreDuration = chunkPlans.Sum(item => item.CoreDurationSeconds);
        var completedCoreDuration = 0d;

        foreach (var chunkPlan in chunkPlans)
        {
            cancellationToken.ThrowIfCancellationRequested();

            var cachePath = Path.Combine(cacheDirectory, $"chunk-{chunkPlan.Sequence:0000}.json");
            var chunkDocument = await TryLoadChunkTranscriptAsync(cachePath, options, cancellationToken);
            if (chunkDocument is null)
            {
                var chunkInputPath = Path.Combine(cacheDirectory, $"chunk-{chunkPlan.Sequence:0000}.wav");
                try
                {
                    var extractionResult = await _audioExtractionService.ExtractAsync(
                        preparedInputPath,
                        chunkInputPath,
                        AudioFormat.Copy,
                        trackIndex: null,
                        startTime: TimeSpan.FromSeconds(chunkPlan.ExtractStartSeconds),
                        duration: TimeSpan.FromSeconds(chunkPlan.ExtractDurationSeconds),
                        normalize: false,
                        bitrateKbps: 192,
                        totalDurationSeconds: chunkPlan.ExtractDurationSeconds,
                        onProgress: null,
                        cancellationToken);

                    if (!extractionResult.Success)
                    {
                        throw new InvalidOperationException(extractionResult.ErrorMessage ?? "Whisper 分块音频提取失败。");
                    }

                    var json = await ExecuteWhisperAsync(
                        chunkInputPath,
                        executablePath,
                        modelPath,
                        options,
                        chunkPlan.ExtractStartSeconds,
                        new Progress<double>(value =>
                            ReportChunkProgress(progress, completedCoreDuration, chunkPlan.CoreDurationSeconds, totalCoreDuration, value)),
                        cancellationToken);

                    chunkDocument = ParseChunkTranscriptDocument(
                        audioFilePath,
                        json,
                        chunkPlan.ExtractStartSeconds,
                        chunkPlan.ExtractDurationSeconds,
                        chunkPlan.CoreStartSeconds,
                        chunkPlan.CoreEndSeconds,
                        chunkPlan.IsLastChunk);

                    await SaveChunkTranscriptAsync(cachePath, chunkDocument, cancellationToken);
                }
                finally
                {
                    TryDeleteFile(chunkInputPath);
                }
            }

            mergedSegments.AddRange(chunkDocument.Segments);
            completedCoreDuration += chunkPlan.CoreDurationSeconds;
            progress?.Report(Math.Min(completedCoreDuration / totalCoreDuration * 100d, 100d));
        }

        return MergeChunkTranscripts(audioFilePath, mergedSegments);
    }

    private async Task<TranscriptDocument?> TryLoadChunkTranscriptAsync(
        string cachePath,
        WhisperOptions options,
        CancellationToken cancellationToken)
    {
        if (!options.ResumePartialResults || !File.Exists(cachePath))
        {
            return null;
        }

        try
        {
            await using var stream = File.OpenRead(cachePath);
            var document = await JsonSerializer.DeserializeAsync<TranscriptDocument>(stream, CacheJsonOptions, cancellationToken);
            if (document is null)
            {
                return null;
            }

            TranscriptDocumentService.Validate(document);
            AppFileLogger.Write("WhisperCliAdapter", $"复用已缓存的分块转写：{cachePath}");
            return document;
        }
        catch (Exception ex)
        {
            AppFileLogger.Write("WhisperCliAdapter", $"读取分块缓存失败，将重新转写：{cachePath} | {ex.Message}");
            TryDeleteFile(cachePath);
            return null;
        }
    }

    private static async Task SaveChunkTranscriptAsync(string cachePath, TranscriptDocument document, CancellationToken cancellationToken)
    {
        var directory = Path.GetDirectoryName(cachePath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        await using var stream = File.Create(cachePath);
        await JsonSerializer.SerializeAsync(stream, document, CacheJsonOptions, cancellationToken);
    }

    private async Task<string> ExecuteWhisperAsync(
        string inputWavPath,
        string executablePath,
        string modelPath,
        WhisperOptions options,
        double startOffsetSeconds,
        IProgress<double>? progress,
        CancellationToken cancellationToken)
    {
        var outputJsonPath = $"{inputWavPath}.json";
        TryDeleteFile(outputJsonPath);

        try
        {
            var startInfo = new ProcessStartInfo
            {
                FileName = executablePath,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            foreach (var argument in BuildArguments(inputWavPath, modelPath, options, startOffsetSeconds))
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

            return await File.ReadAllTextAsync(outputJsonPath, cancellationToken);
        }
        finally
        {
            TryDeleteFile(outputJsonPath);
        }
    }

    private static TranscriptDocument ParseTranscriptDocument(
        string audioFilePath,
        string json,
        double? filterStartSeconds,
        double? filterEndSeconds,
        bool isLastChunk)
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
            .Select(item => new TranscriptSegment
            {
                Id = string.Empty,
                Start = (item.Offsets?.From ?? 0) / 1000d,
                End = (item.Offsets?.To ?? 0) / 1000d,
                Text = item.Text?.Trim() ?? string.Empty,
                Source = "whisper.cpp",
                Channel = "mono"
            })
            .Where(item => ShouldKeepSegment(item, filterStartSeconds, filterEndSeconds, isLastChunk))
            .ToList() ?? [];

        for (var index = 0; index < segments.Count; index++)
        {
            segments[index] = CloneWithId(segments[index], $"seg_{index + 1:000}");
        }

        return new TranscriptDocument
        {
            AudioPath = audioFilePath,
            Segments = segments
        };
    }

    private static TranscriptDocument ParseChunkTranscriptDocument(
        string audioFilePath,
        string json,
        double chunkOffsetSeconds,
        double chunkDurationSeconds,
        double coreStartSeconds,
        double coreEndSeconds,
        bool isLastChunk)
    {
        var document = ParseTranscriptDocument(
            audioFilePath,
            json,
            filterStartSeconds: null,
            filterEndSeconds: null,
            isLastChunk: true);

        var normalizedSegments = NormalizeChunkSegmentOffsets(
            document.Segments,
            chunkOffsetSeconds,
            chunkDurationSeconds);

        var filteredSegments = normalizedSegments
            .Where(item => ShouldKeepSegment(item, coreStartSeconds, coreEndSeconds, isLastChunk))
            .Select((item, index) => CloneWithId(item, $"seg_{index + 1:000}"))
            .ToList();

        return new TranscriptDocument
        {
            AudioPath = audioFilePath,
            Segments = filteredSegments
        };
    }

    private static IReadOnlyList<string> BuildArguments(string inputWavPath, string modelPath, WhisperOptions options, double startOffsetSeconds)
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

        if (startOffsetSeconds > 0d && !UsesVoiceActivityDetection(options.ExtraArgs))
        {
            arguments.Add("-ot");
            arguments.Add(((int)Math.Round(startOffsetSeconds * 1000d, MidpointRounding.AwayFromZero)).ToString(CultureInfo.InvariantCulture));
        }

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

    private static bool UsesVoiceActivityDetection(string extraArgs)
    {
        return SplitExtraArguments(extraArgs)
            .Any(argument => string.Equals(argument, "--vad", StringComparison.OrdinalIgnoreCase));
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

    private static bool ShouldChunk(double durationSeconds, WhisperOptions options)
    {
        return options.ChunkDurationSeconds > 0 &&
               durationSeconds > options.ChunkDurationSeconds + 0.001d;
    }

    private static double ReadWaveDurationSeconds(string path)
    {
        using var stream = File.OpenRead(path);
        using var reader = new BinaryReader(stream, Encoding.ASCII, leaveOpen: false);

        if (stream.Length < 44)
        {
            throw new InvalidOperationException($"WAV 文件过小，无法读取时长：{path}");
        }

        var riff = new string(reader.ReadChars(4));
        _ = reader.ReadUInt32();
        var wave = new string(reader.ReadChars(4));
        if (!string.Equals(riff, "RIFF", StringComparison.Ordinal) ||
            !string.Equals(wave, "WAVE", StringComparison.Ordinal))
        {
            throw new InvalidOperationException($"不是有效的 WAV 文件：{path}");
        }

        ushort channels = 0;
        uint sampleRate = 0;
        ushort bitsPerSample = 0;
        uint dataSize = 0;

        while (stream.Position + 8 <= stream.Length)
        {
            var chunkId = new string(reader.ReadChars(4));
            var chunkSize = reader.ReadUInt32();

            if (string.Equals(chunkId, "fmt ", StringComparison.Ordinal))
            {
                _ = reader.ReadUInt16();
                channels = reader.ReadUInt16();
                sampleRate = reader.ReadUInt32();
                _ = reader.ReadUInt32();
                _ = reader.ReadUInt16();
                bitsPerSample = reader.ReadUInt16();

                var remaining = chunkSize - 16;
                if (remaining > 0)
                {
                    stream.Seek(remaining, SeekOrigin.Current);
                }
            }
            else if (string.Equals(chunkId, "data", StringComparison.Ordinal))
            {
                dataSize = chunkSize;
                break;
            }
            else
            {
                stream.Seek(chunkSize, SeekOrigin.Current);
            }

            if ((chunkSize & 1) == 1 && stream.Position < stream.Length)
            {
                stream.Seek(1, SeekOrigin.Current);
            }
        }

        var bytesPerSecond = sampleRate * channels * (bitsPerSample / 8d);
        if (bytesPerSecond <= 0 || dataSize == 0)
        {
            throw new InvalidOperationException($"WAV 文件缺少可用的音频格式或数据区：{path}");
        }

        return dataSize / bytesPerSecond;
    }

    private static List<TranscriptionChunkPlan> BuildChunkPlans(double durationSeconds, WhisperOptions options)
    {
        var chunkDurationSeconds = Math.Max(options.ChunkDurationSeconds, 1);
        var overlapSeconds = Math.Max(options.ChunkOverlapSeconds, 0d);
        var plans = new List<TranscriptionChunkPlan>();
        var sequence = 1;

        for (var coreStart = 0d; coreStart < durationSeconds - 0.001d; coreStart += chunkDurationSeconds)
        {
            var coreEnd = Math.Min(coreStart + chunkDurationSeconds, durationSeconds);
            var extractStart = Math.Max(0d, coreStart - overlapSeconds);
            var extractEnd = Math.Min(durationSeconds, coreEnd + overlapSeconds);
            plans.Add(new TranscriptionChunkPlan(
                sequence++,
                coreStart,
                coreEnd,
                extractStart,
                extractEnd,
                coreEnd >= durationSeconds - 0.001d));
        }

        return plans;
    }

    private static string BuildChunkCacheDirectory(string audioFilePath, WhisperOptions options)
    {
        var audioInfo = new FileInfo(audioFilePath);
        var signatureSource = string.Join("|",
            Path.GetFullPath(audioFilePath),
            audioInfo.Length.ToString(CultureInfo.InvariantCulture),
            audioInfo.LastWriteTimeUtc.Ticks.ToString(CultureInfo.InvariantCulture),
            Path.GetFullPath(options.ModelPath),
            options.Language,
            options.Threads.ToString(CultureInfo.InvariantCulture),
            options.ExtraArgs,
            options.ChunkDurationSeconds.ToString(CultureInfo.InvariantCulture),
            options.ChunkOverlapSeconds.ToString("0.###", CultureInfo.InvariantCulture));

        var signatureBytes = SHA256.HashData(Encoding.UTF8.GetBytes(signatureSource));
        var signature = Convert.ToHexString(signatureBytes[..8]).ToLowerInvariant();
        var parentDirectory = Path.GetDirectoryName(audioFilePath) ?? Path.GetTempPath();
        var cacheDirectoryName = $"{Path.GetFileNameWithoutExtension(audioFilePath)}.whisper-chunks.{signature}";
        return Path.Combine(parentDirectory, cacheDirectoryName);
    }

    private static void ReportChunkProgress(
        IProgress<double>? progress,
        double completedCoreDuration,
        double currentChunkDuration,
        double totalCoreDuration,
        double currentChunkPercent)
    {
        if (progress is null || totalCoreDuration <= 0d)
        {
            return;
        }

        var clampedPercent = Math.Max(0d, Math.Min(currentChunkPercent, 100d));
        var completedWithCurrent = completedCoreDuration + currentChunkDuration * (clampedPercent / 100d);
        progress.Report(Math.Min(completedWithCurrent / totalCoreDuration * 100d, 100d));
    }

    private static bool ShouldKeepSegment(
        TranscriptSegment segment,
        double? filterStartSeconds,
        double? filterEndSeconds,
        bool isLastChunk)
    {
        if (!filterStartSeconds.HasValue || !filterEndSeconds.HasValue)
        {
            return true;
        }

        var midpoint = (segment.Start + segment.End) / 2d;
        if (midpoint < filterStartSeconds.Value)
        {
            return false;
        }

        return isLastChunk
            ? midpoint <= filterEndSeconds.Value + 0.001d
            : midpoint < filterEndSeconds.Value;
    }

    private static List<TranscriptSegment> NormalizeChunkSegmentOffsets(
        IReadOnlyList<TranscriptSegment> segments,
        double chunkOffsetSeconds,
        double chunkDurationSeconds)
    {
        if (segments.Count == 0)
        {
            return [];
        }

        var appearsRelativeToChunk = chunkOffsetSeconds > 0.001d &&
                                     segments.Min(item => item.Start) < chunkOffsetSeconds - 0.05d;

        if (!appearsRelativeToChunk)
        {
            return segments.ToList();
        }

        return segments
            .Select(item => new TranscriptSegment
            {
                Id = item.Id,
                Start = item.Start + chunkOffsetSeconds,
                End = item.End + chunkOffsetSeconds,
                Text = item.Text,
                Language = item.Language,
                Speaker = item.Speaker,
                Confidence = item.Confidence,
                Source = item.Source,
                Overlap = item.Overlap,
                Channel = item.Channel
            })
            .ToList();
    }

    private static TranscriptSegment CloneWithId(TranscriptSegment segment, string id)
    {
        return new TranscriptSegment
        {
            Id = id,
            Start = segment.Start,
            End = segment.End,
            Text = segment.Text,
            Language = segment.Language,
            Speaker = segment.Speaker,
            Confidence = segment.Confidence,
            Source = segment.Source,
            Overlap = segment.Overlap,
            Channel = segment.Channel
        };
    }

    private static TranscriptDocument MergeChunkTranscripts(string audioFilePath, IEnumerable<TranscriptSegment> segments)
    {
        var ordered = segments
            .OrderBy(item => item.Start)
            .ThenBy(item => item.End)
            .ThenBy(item => item.Text, StringComparer.Ordinal)
            .ToList();

        var deduplicated = new List<TranscriptSegment>(ordered.Count);
        foreach (var segment in ordered)
        {
            if (deduplicated.Count > 0 && AreEffectivelySameSegment(deduplicated[^1], segment))
            {
                continue;
            }

            deduplicated.Add(segment);
        }

        var normalized = deduplicated
            .Select((segment, index) => CloneWithId(segment, $"seg_{index + 1:000}"))
            .ToList();

        return new TranscriptDocument
        {
            AudioPath = audioFilePath,
            Segments = normalized
        };
    }

    private static bool AreEffectivelySameSegment(TranscriptSegment left, TranscriptSegment right)
    {
        return Math.Abs(left.Start - right.Start) <= 0.05d &&
               Math.Abs(left.End - right.End) <= 0.05d &&
               string.Equals(left.Text, right.Text, StringComparison.Ordinal);
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

    private sealed record TranscriptionChunkPlan(
        int Sequence,
        double CoreStartSeconds,
        double CoreEndSeconds,
        double ExtractStartSeconds,
        double ExtractEndSeconds,
        bool IsLastChunk)
    {
        public double CoreDurationSeconds => Math.Max(CoreEndSeconds - CoreStartSeconds, 0d);
        public double ExtractDurationSeconds => Math.Max(ExtractEndSeconds - ExtractStartSeconds, 0d);
    }
}
