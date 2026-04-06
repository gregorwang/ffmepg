using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Diagnostics;
using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class NativeMediaCoreService
{
    private const int BufferCapacity = 64 * 1024;
    private readonly object _libraryLock = new();
    private IntPtr _libraryHandle;
    private ProbeMediaJsonDelegate? _probeDelegate;
    private ValidateOutputJsonDelegate? _validateOutputDelegate;
    private AnalyzeSubtitlesJsonDelegate? _analyzeDelegate;
    private ListAudioTracksJsonDelegate? _listAudioTracksDelegate;
    private ExtractAudioJsonDelegate? _extractAudioDelegate;
    private DetectSilenceJsonDelegate? _detectSilenceDelegate;
    private FastClipJsonDelegate? _fastClipDelegate;
    private DetectScenesJsonDelegate? _detectScenesDelegate;
    private SampleFramePngJsonDelegate? _sampleFrameDelegate;
    private SampleFramesBatchJsonDelegate? _sampleFramesBatchDelegate;
    private string? _loadedLibraryPath;
    private string? _loadFailureMessage;

    public bool IsNativeBinaryPresent => ResolveNativeDllPath() is not null;

    public string StatusSummary
    {
        get
        {
            if (!IsNativeBinaryPresent)
            {
                return "原生字幕分析未就绪，将回退到 ffprobe";
            }

            if (!string.IsNullOrWhiteSpace(_loadFailureMessage))
            {
                return $"原生字幕分析加载失败，将回退到 ffprobe | {_loadFailureMessage}";
            }

            if (!string.IsNullOrWhiteSpace(_loadedLibraryPath))
            {
                return $"原生字幕分析可用 | {Path.GetFileName(_loadedLibraryPath)}";
            }

            return "原生字幕分析可用";
        }
    }

    public async Task<NativeSubtitleAnalysisResult> AnalyzeSubtitlesAsync(
        string mediaPath,
        IReadOnlyList<SubtitleTrackInfo> fallbackTracks,
        CancellationToken cancellationToken = default)
    {
        if (!EnsureNativeLibraryLoaded())
        {
            return CreateFallbackResult("未找到 AnimeMediaCore.dll，将使用 ffprobe 字幕信息。", fallbackTracks);
        }

        return await Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                var buffer = new StringBuilder(BufferCapacity);
                var exitCode = _analyzeDelegate!(mediaPath, buffer, buffer.Capacity);

                if (exitCode != 0 || buffer.Length == 0)
                {
                    AppFileLogger.Write("NativeMediaCoreService", $"原生字幕分析返回代码 {exitCode}，已回退。输入：{mediaPath}");
                    return CreateFallbackResult($"原生字幕分析返回代码 {exitCode}，已回退。", fallbackTracks);
                }

                var payload = JsonSerializer.Deserialize<NativeSubtitlePayload>(buffer.ToString());
                if (payload?.subtitle_tracks is null || payload.subtitle_tracks.Count == 0)
                {
                    AppFileLogger.Write("NativeMediaCoreService", $"原生字幕分析未返回轨道，已回退。输入：{mediaPath}");
                    return CreateFallbackResult("原生字幕分析未返回可用轨道，已回退。", fallbackTracks);
                }

                var tracks = payload.subtitle_tracks.Select(track => new SubtitleTrackInfo
                {
                    Index = track.index,
                    Title = track.title ?? string.Empty,
                    Language = track.language ?? string.Empty,
                    IsDefault = track.is_default,
                    CodecName = track.codec_name ?? string.Empty,
                    TextSample = track.text_sample ?? string.Empty,
                    AnalysisSource = "native"
                }).ToList();

                return new NativeSubtitleAnalysisResult
                {
                    IsAvailable = true,
                    IsFallback = false,
                    Source = "native",
                    Message = payload.message ?? "已使用原生字幕分析",
                    SubtitleTracks = tracks
                };
            }
            catch (Exception ex) when (ex is JsonException or DecoderFallbackException)
            {
                AppFileLogger.WriteException("NativeMediaCoreService", ex);
                return CreateFallbackResult($"原生字幕分析结果解析失败：{ex.Message}", fallbackTracks);
            }
            catch (Exception ex)
            {
                AppFileLogger.WriteException("NativeMediaCoreService", ex);
                return CreateFallbackResult($"原生字幕分析结果解析失败：{ex.Message}", fallbackTracks);
            }
        }, cancellationToken);
    }

    public async Task<MediaProbeResult?> ProbeMediaAsync(string mediaPath, CancellationToken cancellationToken = default)
    {
        if (!EnsureNativeLibraryLoaded() || _probeDelegate is null)
        {
            return null;
        }

        return await Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();

            try
            {
                var buffer = new StringBuilder(BufferCapacity);
                var exitCode = _probeDelegate(mediaPath, buffer, buffer.Capacity);
                if (exitCode != 0 || buffer.Length == 0)
                {
                    AppFileLogger.Write("NativeMediaCoreService", $"原生媒体探测返回代码 {exitCode}，将回退到 ffprobe。输入：{mediaPath}");
                    return null;
                }

                var payload = JsonSerializer.Deserialize<NativeMediaProbePayload>(buffer.ToString());
                if (payload is null || payload.file_exists is false)
                {
                    AppFileLogger.Write("NativeMediaCoreService", $"原生媒体探测未返回有效文件信息，已回退。输入：{mediaPath}");
                    return null;
                }

                return new MediaProbeResult
                {
                    Path = payload.input_path ?? mediaPath,
                    Duration = TimeSpan.FromSeconds(payload.duration_seconds),
                    AudioTracks = payload.audio_tracks.Select(track => new AudioTrackInfo
                    {
                        Index = track.index,
                        StreamIndex = track.stream_index,
                        CodecName = track.codec_name ?? string.Empty,
                        Language = track.language ?? string.Empty,
                        Title = track.title ?? string.Empty,
                        Channels = track.channels,
                        SampleRate = track.sample_rate,
                        BitRate = track.bit_rate,
                        IsDefault = track.is_default
                    }).ToList(),
                    SubtitleTracks = payload.subtitle_tracks.Select(track => new SubtitleTrackInfo
                    {
                        Index = track.index,
                        Title = track.title ?? string.Empty,
                        Language = track.language ?? string.Empty,
                        IsDefault = track.is_default,
                        CodecName = track.codec_name ?? string.Empty,
                        TextSample = track.text_sample ?? string.Empty,
                        AnalysisSource = "native"
                    }).ToList(),
                    AnalysisSource = "native",
                    Message = payload.message ?? "已通过原生模块完成媒体探测"
                };
            }
            catch (Exception ex)
            {
                AppFileLogger.WriteException("NativeMediaCoreService", ex);
                return null;
            }
        }, cancellationToken);
    }

    public async Task<OutputValidationResult?> ValidateOutputAsync(
        string inputPath,
        string outputPath,
        int toleranceSeconds = 5,
        CancellationToken cancellationToken = default)
    {
        if (!EnsureNativeLibraryLoaded() || _validateOutputDelegate is null)
        {
            return null;
        }

        return await Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();

            try
            {
                var buffer = new StringBuilder(BufferCapacity);
                var exitCode = _validateOutputDelegate(inputPath, outputPath, toleranceSeconds, buffer, buffer.Capacity);
                if (exitCode != 0 || buffer.Length == 0)
                {
                    AppFileLogger.Write("NativeMediaCoreService", $"原生输出校验返回代码 {exitCode}，将回退到 ffprobe。输入：{inputPath}");
                    return null;
                }

                var payload = JsonSerializer.Deserialize<NativeOutputValidationPayload>(buffer.ToString());
                if (payload is null)
                {
                    AppFileLogger.Write("NativeMediaCoreService", $"原生输出校验未返回有效载荷，已回退。输入：{inputPath}");
                    return null;
                }

                return new OutputValidationResult
                {
                    IsMatch = payload.is_match,
                    IsFallback = false,
                    Source = "native",
                    Message = payload.message ?? "已通过原生模块完成输出校验",
                    InputDurationSeconds = payload.input_duration_seconds,
                    OutputDurationSeconds = payload.output_duration_seconds,
                    DifferenceSeconds = payload.difference_seconds
                };
            }
            catch (Exception ex)
            {
                AppFileLogger.WriteException("NativeMediaCoreService", ex);
                return null;
            }
        }, cancellationToken);
    }

    public async Task<IReadOnlyList<AudioTrackInfo>?> ListAudioTracksAsync(string mediaPath, CancellationToken cancellationToken = default)
    {
        if (!EnsureNativeLibraryLoaded() || _listAudioTracksDelegate is null)
        {
            return null;
        }

        return await Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();

            try
            {
                var buffer = new StringBuilder(BufferCapacity);
                var exitCode = _listAudioTracksDelegate(mediaPath, buffer, buffer.Capacity);
                if (exitCode != 0 || buffer.Length == 0)
                {
                    AppFileLogger.Write("NativeMediaCoreService", $"原生音轨探测返回代码 {exitCode}，将回退到 ffprobe。输入：{mediaPath}");
                    return null;
                }

                var payload = JsonSerializer.Deserialize<NativeAudioTracksPayload>(buffer.ToString());
                return payload?.audio_tracks.Select(track => new AudioTrackInfo
                {
                    Index = track.index,
                    StreamIndex = track.stream_index,
                    CodecName = track.codec_name ?? string.Empty,
                    Language = track.language ?? string.Empty,
                    Title = track.title ?? string.Empty,
                    Channels = track.channels,
                    SampleRate = track.sample_rate,
                    BitRate = track.bit_rate,
                    IsDefault = track.is_default
                }).ToList();
            }
            catch (Exception ex)
            {
                AppFileLogger.WriteException("NativeMediaCoreService", ex);
                return null;
            }
        }, cancellationToken);
    }

    public async Task<AudioExtractionResult?> ExtractAudioAsync(
        string inputPath,
        string outputPath,
        AudioFormat format,
        int? trackIndex,
        int bitrateKbps,
        bool normalize,
        CancellationToken cancellationToken = default)
    {
        if (!EnsureNativeLibraryLoaded() || _extractAudioDelegate is null)
        {
            return null;
        }

        return await Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();

            try
            {
                var buffer = new StringBuilder(BufferCapacity);
                var exitCode = _extractAudioDelegate(
                    inputPath,
                    outputPath,
                    trackIndex ?? -1,
                    format.ToString(),
                    bitrateKbps,
                    normalize ? 1 : 0,
                    buffer,
                    buffer.Capacity);

                if (exitCode != 0 || buffer.Length == 0)
                {
                    AppFileLogger.Write("NativeMediaCoreService", $"原生音频提取返回代码 {exitCode}，将回退到 ffmpeg。输入：{inputPath}");
                    return null;
                }

                var payload = JsonSerializer.Deserialize<NativeOutputOperationPayload>(buffer.ToString());
                return new AudioExtractionResult
                {
                    Success = payload?.success == true && payload.output_exists,
                    OutputPath = payload?.output_path ?? outputPath,
                    ErrorMessage = payload?.success == true ? null : payload?.details ?? payload?.message ?? "原生音频提取失败"
                };
            }
            catch (Exception ex)
            {
                AppFileLogger.WriteException("NativeMediaCoreService", ex);
                return null;
            }
        }, cancellationToken);
    }

    public async Task<IReadOnlyList<SilenceSegment>?> DetectSilenceAsync(
        string inputPath,
        double noiseThresholdDb,
        double minimumDuration,
        CancellationToken cancellationToken = default)
    {
        if (!EnsureNativeLibraryLoaded() || _detectSilenceDelegate is null)
        {
            return null;
        }

        return await Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();

            try
            {
                var buffer = new StringBuilder(BufferCapacity);
                var exitCode = _detectSilenceDelegate(inputPath, noiseThresholdDb, minimumDuration, buffer, buffer.Capacity);
                if (exitCode != 0 || buffer.Length == 0)
                {
                    AppFileLogger.Write("NativeMediaCoreService", $"原生静音检测返回代码 {exitCode}，将回退到 ffmpeg。输入：{inputPath}");
                    return null;
                }

                var payload = JsonSerializer.Deserialize<NativeSilencePayload>(buffer.ToString());
                return payload?.segments.Select(segment => new SilenceSegment
                {
                    StartSeconds = segment.start_seconds,
                    EndSeconds = segment.end_seconds,
                    DurationSeconds = segment.duration_seconds
                }).ToList();
            }
            catch (Exception ex)
            {
                AppFileLogger.WriteException("NativeMediaCoreService", ex);
                return null;
            }
        }, cancellationToken);
    }

    public async Task<ClipResult?> FastClipAsync(
        string inputPath,
        string outputPath,
        double startSeconds,
        double durationSeconds,
        CancellationToken cancellationToken = default)
    {
        if (!EnsureNativeLibraryLoaded() || _fastClipDelegate is null)
        {
            return null;
        }

        return await Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();

            try
            {
                var buffer = new StringBuilder(BufferCapacity);
                var exitCode = _fastClipDelegate(inputPath, outputPath, startSeconds, durationSeconds, buffer, buffer.Capacity);
                if (exitCode != 0 || buffer.Length == 0)
                {
                    AppFileLogger.Write("NativeMediaCoreService", $"原生快切返回代码 {exitCode}，将回退到 ffmpeg。输入：{inputPath}");
                    return null;
                }

                var payload = JsonSerializer.Deserialize<NativeOutputOperationPayload>(buffer.ToString());
                return new ClipResult
                {
                    Success = payload?.success == true && payload.output_exists,
                    OutputPath = payload?.output_path ?? outputPath,
                    ErrorMessage = payload?.success == true ? null : payload?.details ?? payload?.message ?? "原生无损快切失败"
                };
            }
            catch (Exception ex)
            {
                AppFileLogger.WriteException("NativeMediaCoreService", ex);
                return null;
            }
        }, cancellationToken);
    }

    public async Task<IReadOnlyList<SceneCutPoint>?> DetectScenesAsync(
        string inputPath,
        double threshold,
        CancellationToken cancellationToken = default)
    {
        if (!EnsureNativeLibraryLoaded() || _detectScenesDelegate is null)
        {
            return null;
        }

        return await Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();

            try
            {
                var buffer = new StringBuilder(BufferCapacity);
                var exitCode = _detectScenesDelegate(inputPath, threshold, buffer, buffer.Capacity);
                if (exitCode != 0 || buffer.Length == 0)
                {
                    AppFileLogger.Write("NativeMediaCoreService", $"原生场景检测返回代码 {exitCode}，将回退到 ffmpeg。输入：{inputPath}");
                    return null;
                }

                var payload = JsonSerializer.Deserialize<NativeScenePayload>(buffer.ToString());
                return payload?.scenes.Select(scene => new SceneCutPoint
                {
                    Sequence = scene.sequence,
                    TimeSeconds = scene.time_seconds
                }).ToList();
            }
            catch (Exception ex)
            {
                AppFileLogger.WriteException("NativeMediaCoreService", ex);
                return null;
            }
        }, cancellationToken);
    }

    public async Task<NativeFrameSampleResult> CaptureFrameAsync(
        string mediaPath,
        string outputPath,
        double timeSeconds,
        CancellationToken cancellationToken = default)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(outputPath) ?? AppContext.BaseDirectory);

        if (EnsureNativeLibraryLoaded() && _sampleFrameDelegate is not null)
        {
            var nativeResult = await TryCaptureFrameWithNativeAsync(mediaPath, outputPath, timeSeconds, cancellationToken);
            if (nativeResult.Success)
            {
                return nativeResult;
            }
        }

        return await CaptureFrameWithCliFallbackAsync(mediaPath, outputPath, timeSeconds, cancellationToken);
    }

    public async Task<BatchFrameSampleResult> CaptureDiagnosticFramesAsync(
        string mediaPath,
        string outputDirectory,
        string filePrefix,
        IReadOnlyList<double> sampleTimes,
        CancellationToken cancellationToken = default)
    {
        Directory.CreateDirectory(outputDirectory);
        if (EnsureNativeLibraryLoaded() && _sampleFramesBatchDelegate is not null)
        {
            var nativeResult = await TryCaptureDiagnosticFramesWithNativeAsync(mediaPath, outputDirectory, filePrefix, sampleTimes, cancellationToken);
            if (nativeResult.Success)
            {
                return nativeResult;
            }
        }

        return await CaptureDiagnosticFramesWithCliFallbackAsync(mediaPath, outputDirectory, filePrefix, sampleTimes, cancellationToken);
    }

    private static NativeSubtitleAnalysisResult CreateFallbackResult(string message, IReadOnlyList<SubtitleTrackInfo> fallbackTracks)
    {
        var tracks = fallbackTracks.Select(track => new SubtitleTrackInfo
        {
            Index = track.Index,
            Title = track.Title,
            Language = track.Language,
            IsDefault = track.IsDefault,
            CodecName = track.CodecName,
            TextSample = track.TextSample,
            AnalysisSource = "ffprobe"
        }).ToList();

        return new NativeSubtitleAnalysisResult
        {
            IsAvailable = false,
            IsFallback = true,
            Source = "ffprobe",
            Message = message,
            SubtitleTracks = tracks
        };
    }

    private static string? ResolveNativeDllPath()
    {
        var candidates = new[]
        {
            Path.Combine(AppContext.BaseDirectory, "AnimeMediaCore.dll"),
            Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, @"..\..\..\native\AnimeMediaCore\build\Debug\AnimeMediaCore.dll")),
            Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, @"..\..\..\native\AnimeMediaCore\build\Debug-NMake\AnimeMediaCore.dll")),
            Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, @"..\..\..\native\AnimeMediaCore\build\Release\AnimeMediaCore.dll")),
            Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, @"..\..\..\native\AnimeMediaCore\build\Release-NMake\AnimeMediaCore.dll"))
        };

        return candidates.FirstOrDefault(File.Exists);
    }

    private bool EnsureNativeLibraryLoaded()
    {
        if (_libraryHandle != IntPtr.Zero && _analyzeDelegate is not null)
        {
            return true;
        }

        var dllPath = ResolveNativeDllPath();
        if (dllPath is null)
        {
            return false;
        }

        lock (_libraryLock)
        {
            if (_libraryHandle != IntPtr.Zero && _analyzeDelegate is not null)
            {
                return true;
            }

            try
            {
                _libraryHandle = NativeLibrary.Load(dllPath);
                if (NativeLibrary.TryGetExport(_libraryHandle, "amc_probe_media_json", out var probeExport))
                {
                    _probeDelegate = Marshal.GetDelegateForFunctionPointer<ProbeMediaJsonDelegate>(probeExport);
                }
                if (NativeLibrary.TryGetExport(_libraryHandle, "amc_validate_output_json", out var validateExport))
                {
                    _validateOutputDelegate = Marshal.GetDelegateForFunctionPointer<ValidateOutputJsonDelegate>(validateExport);
                }
                var export = NativeLibrary.GetExport(_libraryHandle, "amc_analyze_subtitles_json");
                _analyzeDelegate = Marshal.GetDelegateForFunctionPointer<AnalyzeSubtitlesJsonDelegate>(export);
                if (NativeLibrary.TryGetExport(_libraryHandle, "amc_list_audio_tracks_json", out var listAudioTracksExport))
                {
                    _listAudioTracksDelegate = Marshal.GetDelegateForFunctionPointer<ListAudioTracksJsonDelegate>(listAudioTracksExport);
                }
                if (NativeLibrary.TryGetExport(_libraryHandle, "amc_extract_audio_json", out var extractAudioExport))
                {
                    _extractAudioDelegate = Marshal.GetDelegateForFunctionPointer<ExtractAudioJsonDelegate>(extractAudioExport);
                }
                if (NativeLibrary.TryGetExport(_libraryHandle, "amc_detect_silence_json", out var detectSilenceExport))
                {
                    _detectSilenceDelegate = Marshal.GetDelegateForFunctionPointer<DetectSilenceJsonDelegate>(detectSilenceExport);
                }
                if (NativeLibrary.TryGetExport(_libraryHandle, "amc_fast_clip_json", out var fastClipExport))
                {
                    _fastClipDelegate = Marshal.GetDelegateForFunctionPointer<FastClipJsonDelegate>(fastClipExport);
                }
                if (NativeLibrary.TryGetExport(_libraryHandle, "amc_detect_scenes_json", out var detectScenesExport))
                {
                    _detectScenesDelegate = Marshal.GetDelegateForFunctionPointer<DetectScenesJsonDelegate>(detectScenesExport);
                }
                if (NativeLibrary.TryGetExport(_libraryHandle, "amc_sample_frame_png_json", out var sampleExport))
                {
                    _sampleFrameDelegate = Marshal.GetDelegateForFunctionPointer<SampleFramePngJsonDelegate>(sampleExport);
                }
                if (NativeLibrary.TryGetExport(_libraryHandle, "amc_sample_frames_batch_json", out var sampleBatchExport))
                {
                    _sampleFramesBatchDelegate = Marshal.GetDelegateForFunctionPointer<SampleFramesBatchJsonDelegate>(sampleBatchExport);
                }
                _loadedLibraryPath = dllPath;
                _loadFailureMessage = null;
                AppFileLogger.Write("NativeMediaCoreService", $"已加载原生模块：{dllPath}");
                return true;
            }
            catch (Exception ex)
            {
                _libraryHandle = IntPtr.Zero;
                _probeDelegate = null;
                _validateOutputDelegate = null;
                _analyzeDelegate = null;
                _listAudioTracksDelegate = null;
                _extractAudioDelegate = null;
                _detectSilenceDelegate = null;
                _fastClipDelegate = null;
                _detectScenesDelegate = null;
                _sampleFrameDelegate = null;
                _sampleFramesBatchDelegate = null;
                _loadedLibraryPath = null;
                _loadFailureMessage = ex.Message;
                AppFileLogger.WriteException("NativeMediaCoreService", ex);
                return false;
            }
        }
    }

    [UnmanagedFunctionPointer(CallingConvention.Cdecl, CharSet = CharSet.Unicode)]
    private delegate int ProbeMediaJsonDelegate(string inputPath, StringBuilder outputJson, int outputCapacity);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl, CharSet = CharSet.Unicode)]
    private delegate int ValidateOutputJsonDelegate(string inputPath, string outputPath, int toleranceSeconds, StringBuilder outputJson, int outputCapacity);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl, CharSet = CharSet.Unicode)]
    private delegate int AnalyzeSubtitlesJsonDelegate(string inputPath, StringBuilder outputJson, int outputCapacity);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl, CharSet = CharSet.Unicode)]
    private delegate int ListAudioTracksJsonDelegate(string inputPath, StringBuilder outputJson, int outputCapacity);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl, CharSet = CharSet.Unicode)]
    private delegate int ExtractAudioJsonDelegate(string inputPath, string outputPath, int trackIndex, string format, int bitrateKbps, int normalize, StringBuilder outputJson, int outputCapacity);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl, CharSet = CharSet.Unicode)]
    private delegate int DetectSilenceJsonDelegate(string inputPath, double noiseThresholdDb, double minimumDuration, StringBuilder outputJson, int outputCapacity);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl, CharSet = CharSet.Unicode)]
    private delegate int FastClipJsonDelegate(string inputPath, string outputPath, double startSeconds, double durationSeconds, StringBuilder outputJson, int outputCapacity);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl, CharSet = CharSet.Unicode)]
    private delegate int DetectScenesJsonDelegate(string inputPath, double threshold, StringBuilder outputJson, int outputCapacity);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl, CharSet = CharSet.Unicode)]
    private delegate int SampleFramePngJsonDelegate(string inputPath, string outputPath, double timeSeconds, StringBuilder outputJson, int outputCapacity);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl, CharSet = CharSet.Unicode)]
    private delegate int SampleFramesBatchJsonDelegate(string inputPath, string outputDirectory, string filePrefix, string timesCsv, StringBuilder outputJson, int outputCapacity);

    private async Task<NativeFrameSampleResult> TryCaptureFrameWithNativeAsync(
        string mediaPath,
        string outputPath,
        double timeSeconds,
        CancellationToken cancellationToken)
    {
        return await Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();

            try
            {
                var buffer = new StringBuilder(BufferCapacity);
                var exitCode = _sampleFrameDelegate!(mediaPath, outputPath, timeSeconds, buffer, buffer.Capacity);
                if (exitCode != 0 || buffer.Length == 0)
                {
                    AppFileLogger.Write("NativeMediaCoreService", $"原生抽帧返回代码 {exitCode}，将回退到 CLI。输入：{mediaPath}");
                    return new NativeFrameSampleResult
                    {
                        Success = false,
                        IsFallback = true,
                        Source = "native",
                        Message = $"原生抽帧返回代码 {exitCode}。"
                    };
                }

                var payload = JsonSerializer.Deserialize<NativeFrameSamplePayload>(buffer.ToString());
                var success = payload?.output_exists == true && File.Exists(outputPath);
                return new NativeFrameSampleResult
                {
                    Success = success,
                    IsFallback = false,
                    Source = "native",
                    Message = payload?.message ?? "原生抽帧已执行",
                    InputPath = payload?.input_path ?? mediaPath,
                    OutputPath = payload?.output_path ?? outputPath,
                    TimeSeconds = payload?.time_seconds ?? timeSeconds
                };
            }
            catch (Exception ex)
            {
                AppFileLogger.WriteException("NativeMediaCoreService", ex);
                return new NativeFrameSampleResult
                {
                    Success = false,
                    IsFallback = true,
                    Source = "native",
                    Message = $"原生抽帧失败：{ex.Message}"
                };
            }
        }, cancellationToken);
    }

    private static async Task<NativeFrameSampleResult> CaptureFrameWithCliFallbackAsync(
        string mediaPath,
        string outputPath,
        double timeSeconds,
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

        startInfo.ArgumentList.Add("-v");
        startInfo.ArgumentList.Add("error");
        startInfo.ArgumentList.Add("-y");
        startInfo.ArgumentList.Add("-ss");
        startInfo.ArgumentList.Add(Math.Max(0, timeSeconds).ToString("0.000", System.Globalization.CultureInfo.InvariantCulture));
        startInfo.ArgumentList.Add("-i");
        startInfo.ArgumentList.Add(mediaPath);
        startInfo.ArgumentList.Add("-frames:v");
        startInfo.ArgumentList.Add("1");
        startInfo.ArgumentList.Add("-an");
        startInfo.ArgumentList.Add("-sn");
        startInfo.ArgumentList.Add(outputPath);

        using var process = new Process { StartInfo = startInfo };
        process.Start();

        var stdoutTask = process.StandardOutput.ReadToEndAsync();
        var stderrTask = process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync(cancellationToken);

        var stderr = await stderrTask;
        await stdoutTask;

        var success = process.ExitCode == 0 && File.Exists(outputPath);
        if (!success)
        {
            AppFileLogger.Write("NativeMediaCoreService", $"CLI 抽帧失败：{stderr}");
        }

        return new NativeFrameSampleResult
        {
            Success = success,
            IsFallback = true,
            Source = "ffmpeg-cli",
            Message = success ? "已通过 ffmpeg CLI 完成抽帧" : $"ffmpeg CLI 抽帧失败：{stderr}",
            InputPath = mediaPath,
            OutputPath = outputPath,
            TimeSeconds = timeSeconds
        };
    }

    private async Task<BatchFrameSampleResult> TryCaptureDiagnosticFramesWithNativeAsync(
        string mediaPath,
        string outputDirectory,
        string filePrefix,
        IReadOnlyList<double> sampleTimes,
        CancellationToken cancellationToken)
    {
        return await Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();

            try
            {
                var buffer = new StringBuilder(BufferCapacity);
                var timesCsv = string.Join(",", sampleTimes.Select(time => time.ToString("0.000", System.Globalization.CultureInfo.InvariantCulture)));
                var exitCode = _sampleFramesBatchDelegate!(mediaPath, outputDirectory, filePrefix, timesCsv, buffer, buffer.Capacity);

                if (exitCode != 0 || buffer.Length == 0)
                {
                    AppFileLogger.Write("NativeMediaCoreService", $"原生批量抽帧返回代码 {exitCode}，将回退到 CLI。输入：{mediaPath}");
                    return new BatchFrameSampleResult
                    {
                        Success = false,
                        IsFallback = true,
                        Source = "native",
                        Message = $"原生批量抽帧返回代码 {exitCode}。"
                    };
                }

                var payload = JsonSerializer.Deserialize<NativeBatchFrameSamplePayload>(buffer.ToString());
                var samples = payload?.samples.Select(sample => new DiagnosticFrameSample
                {
                    TimeSeconds = sample.time_seconds,
                    OutputPath = sample.output_path ?? string.Empty,
                    OutputExists = sample.output_exists && !string.IsNullOrWhiteSpace(sample.output_path) && File.Exists(sample.output_path)
                }).ToList() ?? [];

                return new BatchFrameSampleResult
                {
                    Success = samples.Count > 0 && samples.All(sample => sample.OutputExists),
                    IsFallback = false,
                    Source = "native",
                    Message = payload?.message ?? "原生批量抽帧已执行",
                    OutputDirectory = payload?.output_directory ?? outputDirectory,
                    Samples = samples
                };
            }
            catch (Exception ex)
            {
                AppFileLogger.WriteException("NativeMediaCoreService", ex);
                return new BatchFrameSampleResult
                {
                    Success = false,
                    IsFallback = true,
                    Source = "native",
                    Message = $"原生批量抽帧失败：{ex.Message}"
                };
            }
        }, cancellationToken);
    }

    private async Task<BatchFrameSampleResult> CaptureDiagnosticFramesWithCliFallbackAsync(
        string mediaPath,
        string outputDirectory,
        string filePrefix,
        IReadOnlyList<double> sampleTimes,
        CancellationToken cancellationToken)
    {
        var samples = new List<DiagnosticFrameSample>();

        for (var i = 0; i < sampleTimes.Count; i++)
        {
            var timeSeconds = sampleTimes[i];
            var fileName = $"{filePrefix}-{i + 1}-{timeSeconds:0.000}s.png";
            var outputPath = Path.Combine(outputDirectory, fileName);
            var result = await CaptureFrameWithCliFallbackAsync(mediaPath, outputPath, timeSeconds, cancellationToken);

            samples.Add(new DiagnosticFrameSample
            {
                TimeSeconds = timeSeconds,
                OutputPath = outputPath,
                OutputExists = result.Success
            });
        }

        return new BatchFrameSampleResult
        {
            Success = samples.Count > 0 && samples.All(sample => sample.OutputExists),
            IsFallback = true,
            Source = "ffmpeg-cli",
            Message = "已通过 ffmpeg CLI 完成批量抽帧",
            OutputDirectory = outputDirectory,
            Samples = samples
        };
    }

    private sealed class NativeSubtitlePayload
    {
        public string? message { get; set; }
        public List<NativeSubtitleTrackPayload> subtitle_tracks { get; set; } = [];
    }

    private sealed class NativeSubtitleTrackPayload
    {
        public int index { get; set; }
        public string? title { get; set; }
        public string? language { get; set; }
        public bool is_default { get; set; }
        public string? codec_name { get; set; }
        public string? text_sample { get; set; }
    }

    private sealed class NativeAudioTrackPayload
    {
        public int index { get; set; }
        public int stream_index { get; set; }
        public string? codec_name { get; set; }
        public string? language { get; set; }
        public string? title { get; set; }
        public int channels { get; set; }
        public int sample_rate { get; set; }
        public long bit_rate { get; set; }
        public bool is_default { get; set; }
    }

    private sealed class NativeAudioTracksPayload
    {
        public string? message { get; set; }
        public string? input_path { get; set; }
        public bool file_exists { get; set; }
        public List<NativeAudioTrackPayload> audio_tracks { get; set; } = [];
    }

    private sealed class NativeOutputOperationPayload
    {
        public string? message { get; set; }
        public string? input_path { get; set; }
        public string? output_path { get; set; }
        public bool file_exists { get; set; }
        public bool output_exists { get; set; }
        public bool success { get; set; }
        public string? details { get; set; }
    }

    private sealed class NativeSilencePayload
    {
        public string? message { get; set; }
        public List<NativeSilenceSegmentPayload> segments { get; set; } = [];
    }

    private sealed class NativeSilenceSegmentPayload
    {
        public double start_seconds { get; set; }
        public double end_seconds { get; set; }
        public double duration_seconds { get; set; }
    }

    private sealed class NativeScenePayload
    {
        public string? message { get; set; }
        public List<NativeSceneCutPayload> scenes { get; set; } = [];
    }

    private sealed class NativeSceneCutPayload
    {
        public int sequence { get; set; }
        public double time_seconds { get; set; }
    }

    private sealed class NativeFrameSamplePayload
    {
        public string? message { get; set; }
        public string? input_path { get; set; }
        public string? output_path { get; set; }
        public bool input_exists { get; set; }
        public bool output_exists { get; set; }
        public double time_seconds { get; set; }
    }

    private sealed class NativeBatchFrameSamplePayload
    {
        public string? message { get; set; }
        public string? input_path { get; set; }
        public string? output_directory { get; set; }
        public List<NativeBatchFrameItemPayload> samples { get; set; } = [];
    }

    private sealed class NativeBatchFrameItemPayload
    {
        public double time_seconds { get; set; }
        public string? output_path { get; set; }
        public bool output_exists { get; set; }
    }

    private sealed class NativeMediaProbePayload
    {
        public string? message { get; set; }
        public string? input_path { get; set; }
        public bool file_exists { get; set; }
        public double duration_seconds { get; set; }
        public List<NativeAudioTrackPayload> audio_tracks { get; set; } = [];
        public List<NativeSubtitleTrackPayload> subtitle_tracks { get; set; } = [];
    }

    private sealed class NativeOutputValidationPayload
    {
        public string? message { get; set; }
        public bool is_match { get; set; }
        public double input_duration_seconds { get; set; }
        public double output_duration_seconds { get; set; }
        public double difference_seconds { get; set; }
    }
}
