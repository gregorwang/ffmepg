using System.Globalization;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class AudioSelectionRenderService
{
    private readonly FfmpegRunner _runner;
    private readonly FfprobeService _ffprobeService;

    public AudioSelectionRenderService(FfmpegRunner runner, FfprobeService ffprobeService)
    {
        _runner = runner;
        _ffprobeService = ffprobeService;
    }

    public async Task<AudioExtractionResult> RenderAsync(
        string inputAudioPath,
        string outputPath,
        TranscriptDocument transcript,
        SelectionDocument selection,
        AudioRenderMode mode,
        Action<double, string>? onProgress,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(inputAudioPath))
        {
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "工作音频文件不存在"
            };
        }

        if (new FileInfo(inputAudioPath).Length == 0)
        {
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "工作音频文件为空"
            };
        }

        var keepIntervals = ResolveKeepIntervals(transcript, selection);
        if (keepIntervals.Count == 0)
        {
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "Selection 没有可保留的片段"
            };
        }

        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrWhiteSpace(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        var arguments = mode == AudioRenderMode.PreserveTimeline
            ? BuildPreserveTimelineArguments(inputAudioPath, outputPath, keepIntervals)
            : BuildConcatArguments(inputAudioPath, outputPath, keepIntervals);

        var totalDurationSeconds = await ResolveTotalDurationSecondsAsync(inputAudioPath, keepIntervals, mode, cancellationToken);

        try
        {
            var result = await _runner.RunAsync(arguments, totalDurationSeconds, onProgress, null, cancellationToken);
            return result.Success
                ? new AudioExtractionResult
                {
                    Success = true,
                    OutputPath = outputPath
                }
                : new AudioExtractionResult
                {
                    Success = false,
                    OutputPath = outputPath,
                    ErrorMessage = result.ErrorMessage
                };
        }
        catch (OperationCanceledException)
        {
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = "已取消"
            };
        }
        catch (Exception ex)
        {
            return new AudioExtractionResult
            {
                Success = false,
                OutputPath = outputPath,
                ErrorMessage = ex.Message
            };
        }
    }

    public static IReadOnlyList<(double Start, double End)> ResolveKeepIntervals(
        TranscriptDocument transcript,
        SelectionDocument selection)
    {
        var transcriptMap = transcript.Segments.ToDictionary(segment => segment.Id, StringComparer.Ordinal);
        var resolvedActions = selection.TargetSegments
            .GroupBy(item => item.SegmentId, StringComparer.Ordinal)
            .ToDictionary(
                group => group.Key,
                group => ResolveAction(group.Select(item => item.Action), selection.ConflictPolicy),
                StringComparer.Ordinal);

        var keepSegments = new List<(double Start, double End)>();
        foreach (var (segmentId, action) in resolvedActions)
        {
            if (!transcriptMap.TryGetValue(segmentId, out var segment))
            {
                throw new InvalidOperationException($"Selection 引用了不存在的 segmentId：{segmentId}");
            }

            if (action == SelectionAction.Keep)
            {
                keepSegments.Add((segment.Start, segment.End));
            }
        }

        return MergeIntervals(keepSegments);
    }

    private async Task<double> ResolveTotalDurationSecondsAsync(
        string inputAudioPath,
        IReadOnlyList<(double Start, double End)> keepIntervals,
        AudioRenderMode mode,
        CancellationToken cancellationToken)
    {
        if (mode == AudioRenderMode.Concat)
        {
            return keepIntervals.Sum(item => item.End - item.Start);
        }

        var probe = await _ffprobeService.ProbeAsync(inputAudioPath, cancellationToken);
        return probe?.Duration.TotalSeconds ?? keepIntervals.Max(item => item.End);
    }

    private static SelectionAction ResolveAction(IEnumerable<SelectionAction> actions, string conflictPolicy)
    {
        var materialized = actions.ToList();
        if (materialized.Count == 0)
        {
            return SelectionAction.Uncertain;
        }

        if (string.Equals(conflictPolicy, "exclude_wins", StringComparison.OrdinalIgnoreCase))
        {
            if (materialized.Contains(SelectionAction.Exclude))
            {
                return SelectionAction.Exclude;
            }

            if (materialized.Contains(SelectionAction.Keep))
            {
                return SelectionAction.Keep;
            }

            return SelectionAction.Uncertain;
        }

        return materialized.Last();
    }

    private static List<(double Start, double End)> MergeIntervals(IEnumerable<(double Start, double End)> intervals)
    {
        var ordered = intervals
            .Where(item => item.End > item.Start)
            .OrderBy(item => item.Start)
            .ToList();

        if (ordered.Count == 0)
        {
            return [];
        }

        var merged = new List<(double Start, double End)> { ordered[0] };
        for (var index = 1; index < ordered.Count; index++)
        {
            var current = ordered[index];
            var last = merged[^1];
            if (current.Start <= last.End + 0.02d)
            {
                merged[^1] = (last.Start, Math.Max(last.End, current.End));
                continue;
            }

            merged.Add(current);
        }

        return merged;
    }

    private static IReadOnlyList<string> BuildPreserveTimelineArguments(
        string inputAudioPath,
        string outputPath,
        IReadOnlyList<(double Start, double End)> keepIntervals)
    {
        var expression = string.Join(
            "+",
            keepIntervals.Select(interval =>
                $"between(t\\,{FormatDecimal(interval.Start)}\\,{FormatDecimal(interval.End)})"));

        var args = new List<string>
        {
            "-y",
            "-hide_banner",
            "-nostats",
            "-progress",
            "pipe:1",
            "-i",
            inputAudioPath,
            "-vn",
            "-sn",
            "-af",
            $"volume='if({expression},1,0)'"
        };

        AppendEncodingArguments(args, outputPath);
        args.Add(outputPath);
        return args;
    }

    private static IReadOnlyList<string> BuildConcatArguments(
        string inputAudioPath,
        string outputPath,
        IReadOnlyList<(double Start, double End)> keepIntervals)
    {
        var filterParts = new List<string>();
        var segmentLabels = new List<string>();

        for (var index = 0; index < keepIntervals.Count; index++)
        {
            var interval = keepIntervals[index];
            var duration = interval.End - interval.Start;
            var label = $"s{index}";
            segmentLabels.Add($"[{label}]");

            var part = $"[0:a:0]atrim=start={FormatDecimal(interval.Start)}:end={FormatDecimal(interval.End)},asetpts=PTS-STARTPTS";
            if (duration >= 0.12d)
            {
                var fadeInDuration = Math.Min(0.05d, duration / 2d);
                var fadeOutDuration = Math.Min(0.05d, duration / 2d);
                var fadeOutStart = Math.Max(duration - fadeOutDuration, 0d);
                part +=
                    $",afade=t=in:st=0:d={FormatDecimal(fadeInDuration)},afade=t=out:st={FormatDecimal(fadeOutStart)}:d={FormatDecimal(fadeOutDuration)}";
            }

            part += $"[{label}]";
            filterParts.Add(part);
        }

        filterParts.Add($"{string.Join(string.Empty, segmentLabels)}concat=n={keepIntervals.Count}:v=0:a=1[aout]");

        var args = new List<string>
        {
            "-y",
            "-hide_banner",
            "-nostats",
            "-progress",
            "pipe:1",
            "-i",
            inputAudioPath,
            "-vn",
            "-sn",
            "-filter_complex",
            string.Join(';', filterParts),
            "-map",
            "[aout]"
        };

        AppendEncodingArguments(args, outputPath);
        args.Add(outputPath);
        return args;
    }

    private static void AppendEncodingArguments(ICollection<string> args, string outputPath)
    {
        var extension = Path.GetExtension(outputPath).ToLowerInvariant();
        switch (extension)
        {
            case ".wav":
                args.Add("-c:a");
                args.Add("pcm_s16le");
                break;
            case ".flac":
                args.Add("-c:a");
                args.Add("flac");
                break;
            case ".mp3":
                args.Add("-c:a");
                args.Add("libmp3lame");
                args.Add("-q:a");
                args.Add("2");
                break;
            default:
                args.Add("-c:a");
                args.Add("aac");
                args.Add("-profile:a");
                args.Add("aac_low");
                args.Add("-b:a");
                args.Add("192k");
                break;
        }
    }

    private static string FormatDecimal(double value)
    {
        return value.ToString("0.###", CultureInfo.InvariantCulture);
    }
}
