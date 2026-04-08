using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Xml.Linq;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class DanmakuAssGeneratorService
{
    private const int PlayResX = 1920;
    private const int PlayResY = 1080;
    private readonly DanmakuCacheService _cacheService;

    public DanmakuAssGeneratorService(DanmakuCacheService cacheService)
    {
        _cacheService = cacheService;
    }

    public async Task<(string AssPath, int KeptComments)> GenerateAsync(
        long cid,
        string xmlPath,
        AppSettings settings,
        IReadOnlySet<string>? excludedCommentKeys,
        Action<string>? logCallback,
        CancellationToken cancellationToken = default)
    {
        if (!File.Exists(xmlPath))
        {
            throw new FileNotFoundException("XML 弹幕文件不存在。", xmlPath);
        }

        var xml = await File.ReadAllTextAsync(xmlPath, cancellationToken);
        var exclusionFingerprint = BuildExcludedCommentFingerprint(excludedCommentKeys);
        var cacheKey = $"{cid}|{BuildSettingsFingerprint(settings)}|{exclusionFingerprint}";
        var ass = await _cacheService.GetOrCreateTextAsync(
            "bilibili-ass",
            cacheKey,
            "ass",
            _ =>
            {
                var comments = ParseComments(xml, settings, excludedCommentKeys);
                return Task.FromResult(BuildAssDocument(comments, settings));
            },
            cancellationToken);

        var keptComments = ass.Split(Environment.NewLine)
            .Count(line => line.StartsWith("Dialogue:", StringComparison.Ordinal));
        var assPath = _cacheService.GetCachePath("bilibili-ass", cacheKey, "ass");
        logCallback?.Invoke($"ASS 生成完成：cid={cid} | 保留弹幕 {keptComments} | {assPath}");
        return (assPath, keptComments);
    }

    public async Task<(string AssPath, int XmlCommentCount, int KeptComments)> GenerateFromXmlAsync(
        string sourceKey,
        string xmlPath,
        AppSettings settings,
        IReadOnlySet<string>? excludedCommentKeys,
        Action<string>? logCallback,
        CancellationToken cancellationToken = default)
    {
        if (!File.Exists(xmlPath))
        {
            throw new FileNotFoundException("XML 弹幕文件不存在。", xmlPath);
        }

        var xml = await File.ReadAllTextAsync(xmlPath, cancellationToken);
        var exclusionFingerprint = BuildExcludedCommentFingerprint(excludedCommentKeys);
        var cacheKey = $"{sourceKey}|{BuildSettingsFingerprint(settings)}|{exclusionFingerprint}|{new FileInfo(xmlPath).LastWriteTimeUtc.Ticks}";
        var comments = ParseComments(xml, settings, excludedCommentKeys);
        var ass = await _cacheService.GetOrCreateTextAsync(
            "local-ass",
            cacheKey,
            "ass",
            _ => Task.FromResult(BuildAssDocument(comments, settings)),
            cancellationToken);

        var keptComments = ass.Split(Environment.NewLine)
            .Count(line => line.StartsWith("Dialogue:", StringComparison.Ordinal));
        var assPath = _cacheService.GetCachePath("local-ass", cacheKey, "ass");
        logCallback?.Invoke($"本地 XML 转 ASS 完成：保留弹幕 {keptComments} | {assPath}");
        return (assPath, CountComments(xml), keptComments);
    }

    public IReadOnlyList<DanmakuComment> ParseComments(string xml, AppSettings settings, IReadOnlySet<string>? excludedCommentKeys = null)
    {
        var blockWords = ParseBlockWords(settings.DanmakuBlockKeywords);
        var document = XDocument.Parse(xml);
        var rawComments = document
            .Descendants("d")
            .Select(TryParseComment)
            .Where(comment => comment is not null)
            .Select(comment => comment!)
            .Where(comment => !string.IsNullOrWhiteSpace(comment.Content))
            .Where(comment => !settings.DanmakuFilterSpecialTypes || (comment.Mode != 7 && comment.Mode != 8))
            .Where(comment => !blockWords.Any(word => comment.Content.Contains(word, StringComparison.OrdinalIgnoreCase)))
            .Where(comment => excludedCommentKeys is null || !excludedCommentKeys.Contains(BuildCommentKey(comment.TimeSeconds, comment.Mode, comment.Content)))
            .Select(comment => new DanmakuComment
            {
                Key = BuildCommentKey(Math.Max(0, comment.TimeSeconds + settings.DanmakuTimeOffsetSeconds), comment.Mode, comment.Content.Trim()),
                TimeSeconds = Math.Max(0, comment.TimeSeconds + settings.DanmakuTimeOffsetSeconds),
                Mode = comment.Mode,
                FontSize = comment.FontSize,
                Color = comment.Color,
                Content = comment.Content.Trim()
            })
            .OrderBy(comment => comment.TimeSeconds)
            .ToList();

        return ApplyDensity(rawComments, settings.DanmakuDensity);
    }

    public async Task<DanmakuAnalysisSnapshot> AnalyzeXmlFileAsync(
        string xmlPath,
        AppSettings settings,
        IReadOnlySet<string>? excludedCommentKeys = null,
        CancellationToken cancellationToken = default)
    {
        if (!File.Exists(xmlPath))
        {
            throw new FileNotFoundException("XML 弹幕文件不存在。", xmlPath);
        }

        var xml = await File.ReadAllTextAsync(xmlPath, cancellationToken);
        var comments = ParseComments(xml, settings, excludedCommentKeys);
        return new DanmakuAnalysisSnapshot
        {
            XmlPath = xmlPath,
            XmlCommentCount = CountComments(xml),
            KeptCommentCount = comments.Count,
            Comments = comments
        };
    }

    public string BuildAssDocument(IReadOnlyList<DanmakuComment> comments, AppSettings settings)
    {
        var culture = CultureInfo.InvariantCulture;
        var builder = new StringBuilder();
        builder.AppendLine("[Script Info]");
        builder.AppendLine("ScriptType: v4.00+");
        builder.AppendLine("WrapStyle: 2");
        builder.AppendLine("ScaledBorderAndShadow: yes");
        builder.AppendLine($"PlayResX: {PlayResX}");
        builder.AppendLine($"PlayResY: {PlayResY}");
        builder.AppendLine("Collisions: Normal");
        builder.AppendLine();
        builder.AppendLine("[V4+ Styles]");
        builder.AppendLine("Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut," +
                           "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding");
        builder.AppendLine($"Style: Danmaku,{EscapeStyleValue(settings.DanmakuFontName)},{settings.DanmakuFontSize},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,7,16,16,16,1");
        builder.AppendLine();
        builder.AppendLine("[Events]");
        builder.AppendLine("Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text");

        var lineHeight = Math.Max(settings.DanmakuFontSize + 6, 18);
        var reservedBottom = settings.BurnEmbeddedSubtitles
            ? Math.Max(settings.DanmakuFontSize * 2 + 40, 140)
            : 48;
        var areaTop = 36;
        var areaBottom = string.Equals(settings.DanmakuAreaMode, DanmakuAreaModes.UpperHalf, StringComparison.OrdinalIgnoreCase)
            ? Math.Max(areaTop + lineHeight * 4, PlayResY / 2)
            : Math.Max(areaTop + lineHeight * 4, PlayResY - reservedBottom);
        var availableHeight = Math.Max(lineHeight * 4, areaBottom - areaTop);
        var scrollRows = new double[Math.Max(8, availableHeight / lineHeight)];
        var topRows = new double[Math.Max(4, Math.Min(10, scrollRows.Length / 4))];
        var bottomRows = new double[Math.Max(4, Math.Min(10, scrollRows.Length / 4))];

        foreach (var comment in comments)
        {
            var text = EscapeDialogueText(comment.Content);
            if (string.IsNullOrWhiteSpace(text))
            {
                continue;
            }

            var isBottom = comment.Mode == 4;
            var isTop = comment.Mode == 5;
            var isReverse = comment.Mode == 6;
            var durationSeconds = isTop || isBottom ? 4.2 : 12.0;
            var startSeconds = comment.TimeSeconds;
            var endSeconds = startSeconds + durationSeconds;
            var fontSize = Math.Max(12, settings.DanmakuFontSize);
            var y = 40;
            string animation;

            if (isTop)
            {
                var lane = AcquireLane(topRows, startSeconds, durationSeconds);
                y = areaTop + (lane * lineHeight);
                animation = $"\\an8\\pos({PlayResX / 2},{y})";
            }
            else if (isBottom)
            {
                var lane = AcquireLane(bottomRows, startSeconds, durationSeconds);
                y = areaBottom - 20 - (lane * lineHeight);
                animation = $"\\an2\\pos({PlayResX / 2},{y})";
            }
            else
            {
                var lane = AcquireLane(scrollRows, startSeconds, durationSeconds);
                y = areaTop + (lane * lineHeight);
                var estimatedWidth = Math.Max(120, EstimateTextWidth(text, fontSize));
                animation = isReverse
                    ? $"\\move({-estimatedWidth},{y},{PlayResX + estimatedWidth},{y})"
                    : $"\\move({PlayResX + estimatedWidth},{y},{-estimatedWidth},{y})";
            }

            var colorTag = comment.Color is > 0 and not 16777215
                ? $"\\c{ToAssColor(comment.Color)}"
                : string.Empty;

            builder.AppendLine(
                $"Dialogue: 0,{FormatAssTime(startSeconds, culture)},{FormatAssTime(endSeconds, culture)},Danmaku,,0,0,0,," +
                $"{{\\fs{fontSize}{colorTag}{animation}}}{text}");
        }

        return builder.ToString();
    }

    private static DanmakuComment? TryParseComment(XElement element)
    {
        var parameter = element.Attribute("p")?.Value;
        if (string.IsNullOrWhiteSpace(parameter))
        {
            return null;
        }

        var segments = parameter.Split(',');
        if (segments.Length < 4 ||
            !double.TryParse(segments[0], NumberStyles.Float, CultureInfo.InvariantCulture, out var timeSeconds) ||
            !int.TryParse(segments[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out var mode) ||
            !int.TryParse(segments[2], NumberStyles.Integer, CultureInfo.InvariantCulture, out var fontSize) ||
            !int.TryParse(segments[3], NumberStyles.Integer, CultureInfo.InvariantCulture, out var color))
        {
            return null;
        }

        return new DanmakuComment
        {
            TimeSeconds = timeSeconds,
            Mode = mode,
            FontSize = fontSize,
            Color = color,
            Content = element.Value
        };
    }

    private static IReadOnlyList<DanmakuComment> ApplyDensity(IReadOnlyList<DanmakuComment> comments, double density)
    {
        var normalizedDensity = Math.Clamp(density, 0.05, 1.0);
        if (normalizedDensity >= 0.999)
        {
            return comments;
        }

        return comments
            .GroupBy(comment => (int)Math.Floor(comment.TimeSeconds))
            .SelectMany(group =>
            {
                var ordered = group.OrderBy(comment => comment.TimeSeconds).ToList();
                var keepCount = Math.Max(1, (int)Math.Ceiling(ordered.Count * normalizedDensity));
                return ordered.Take(keepCount);
            })
            .OrderBy(comment => comment.TimeSeconds)
            .ToList();
    }

    private static HashSet<string> ParseBlockWords(string raw)
    {
        return raw
            .Split(['|', '\r', '\n'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(word => !string.IsNullOrWhiteSpace(word))
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
    }

    private static int AcquireLane(double[] lanes, double startSeconds, double durationSeconds)
    {
        for (var index = 0; index < lanes.Length; index++)
        {
            if (lanes[index] <= startSeconds)
            {
                lanes[index] = startSeconds + durationSeconds;
                return index;
            }
        }

        var fallbackIndex = 0;
        var fallbackValue = lanes[0];
        for (var index = 1; index < lanes.Length; index++)
        {
            if (lanes[index] < fallbackValue)
            {
                fallbackValue = lanes[index];
                fallbackIndex = index;
            }
        }

        lanes[fallbackIndex] = startSeconds + durationSeconds;
        return fallbackIndex;
    }

    private static string EscapeDialogueText(string value)
    {
        return value
            .Replace("\\", "＼", StringComparison.Ordinal)
            .Replace("{", "｛", StringComparison.Ordinal)
            .Replace("}", "｝", StringComparison.Ordinal)
            .Replace(Environment.NewLine, "\\N", StringComparison.Ordinal)
            .Replace("\r", string.Empty, StringComparison.Ordinal)
            .Replace("\n", "\\N", StringComparison.Ordinal);
    }

    private static string EscapeStyleValue(string value)
    {
        return value.Replace(",", string.Empty, StringComparison.Ordinal);
    }

    private static int EstimateTextWidth(string text, int fontSize)
    {
        var widthUnits = 0d;
        foreach (var ch in text)
        {
            widthUnits += ch <= 0x007F ? 0.62d : 1.0d;
        }

        return (int)Math.Ceiling(widthUnits * fontSize);
    }

    private static string FormatAssTime(double seconds, CultureInfo culture)
    {
        var time = TimeSpan.FromSeconds(Math.Max(0, seconds));
        return string.Format(
            culture,
            "{0:0}:{1:00}:{2:00}.{3:00}",
            (int)time.TotalHours,
            time.Minutes,
            time.Seconds,
            time.Milliseconds / 10);
    }

    private static string ToAssColor(int rgb)
    {
        var red = rgb >> 16 & 0xFF;
        var green = rgb >> 8 & 0xFF;
        var blue = rgb & 0xFF;
        return $"&H{blue:X2}{green:X2}{red:X2}&";
    }

    private static string BuildSettingsFingerprint(AppSettings settings)
    {
        var raw = string.Join("|",
            settings.DanmakuFontName,
            settings.DanmakuFontSize,
            settings.DanmakuDensity.ToString(CultureInfo.InvariantCulture),
            settings.DanmakuTimeOffsetSeconds.ToString(CultureInfo.InvariantCulture),
            settings.DanmakuBlockKeywords,
            settings.DanmakuFilterSpecialTypes,
            settings.DanmakuAreaMode,
            settings.BurnEmbeddedSubtitles);
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(raw));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }

    private static int CountComments(string xml)
    {
        var document = XDocument.Parse(xml);
        return document.Descendants("d").Count();
    }

    public static string BuildCommentKey(double timeSeconds, int mode, string content)
    {
        return $"{timeSeconds:0.###}|{mode}|{content.Trim()}";
    }

    private static string BuildExcludedCommentFingerprint(IReadOnlySet<string>? excludedCommentKeys)
    {
        if (excludedCommentKeys is null || excludedCommentKeys.Count == 0)
        {
            return "none";
        }

        var raw = string.Join("|", excludedCommentKeys.OrderBy(key => key, StringComparer.Ordinal));
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(raw));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }
}
