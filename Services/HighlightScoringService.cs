using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class HighlightScoringService
{
    private const double SceneWeight = 0.40;
    private const double VolumeWeight = 0.35;
    private const double FilterPenalty = 0.25;

    public IReadOnlyList<HighlightCandidate> Score(
        double totalDurationSeconds,
        IReadOnlyList<SceneCutPoint> sceneCutPoints,
        IReadOnlyList<VolumeSegment> volumeSegments,
        IReadOnlyList<VideoAnalysisSegment> blackSegments,
        IReadOnlyList<VideoAnalysisSegment> freezeSegments,
        double windowSeconds = 10.0,
        int topN = 6)
    {
        if (totalDurationSeconds <= 0 || sceneCutPoints.Count == 0)
        {
            return [];
        }

        var windowCount = (int)Math.Ceiling(totalDurationSeconds / windowSeconds);
        if (windowCount == 0)
        {
            return [];
        }

        var windows = new WindowData[windowCount];
        for (var i = 0; i < windowCount; i++)
        {
            var start = i * windowSeconds;
            var end = Math.Min(start + windowSeconds, totalDurationSeconds);
            windows[i] = new WindowData
            {
                Index = i,
                StartSeconds = start,
                EndSeconds = end,
                DurationSeconds = end - start
            };
        }

        // 1. 计算场景切换密度
        foreach (var cut in sceneCutPoints)
        {
            var windowIndex = (int)(cut.TimeSeconds / windowSeconds);
            if (windowIndex >= 0 && windowIndex < windowCount)
            {
                windows[windowIndex].SceneCutCount++;
            }
        }

        var maxSceneDensity = windows.Max(w => w.SceneCutCount / Math.Max(w.DurationSeconds, 0.01));

        // 2. 计算音量水平
        foreach (var vol in volumeSegments)
        {
            var windowIndex = (int)(vol.StartSeconds / windowSeconds);
            if (windowIndex >= 0 && windowIndex < windowCount && !double.IsNegativeInfinity(vol.MeanVolumeDb))
            {
                windows[windowIndex].VolumeSamples.Add(vol.MeanVolumeDb);
            }
        }

        var allVolumes = windows
            .SelectMany(w => w.VolumeSamples)
            .Where(v => !double.IsNegativeInfinity(v))
            .ToList();
        var minVolume = allVolumes.Count > 0 ? allVolumes.Min() : -60.0;
        var maxVolume = allVolumes.Count > 0 ? allVolumes.Max() : 0.0;
        var volumeRange = Math.Max(maxVolume - minVolume, 0.01);

        // 3. 标记黑场/冻帧区间
        foreach (var black in blackSegments)
        {
            MarkOverlap(windows, black.StartSeconds, black.EndSeconds, windowSeconds, isBlack: true);
        }

        foreach (var freeze in freezeSegments)
        {
            MarkOverlap(windows, freeze.StartSeconds, freeze.EndSeconds, windowSeconds, isBlack: false);
        }

        // 4. 评分
        foreach (var w in windows)
        {
            var sceneDensity = w.SceneCutCount / Math.Max(w.DurationSeconds, 0.01);
            var sceneScore = maxSceneDensity > 0
                ? sceneDensity / maxSceneDensity
                : 0;

            var avgVolume = w.VolumeSamples.Count > 0
                ? w.VolumeSamples.Average()
                : minVolume;
            var volumeScore = (avgVolume - minVolume) / volumeRange;

            var baseScore = (sceneScore * SceneWeight + volumeScore * VolumeWeight) * 100.0;

            // 黑场/冻帧惩罚
            if (w.HasBlack || w.HasFreeze)
            {
                baseScore *= (1.0 - FilterPenalty);
            }

            w.Score = Math.Max(baseScore, 0);
            w.SceneChangeRate = sceneDensity;
            w.AverageVolume = avgVolume;
        }

        // 5. 合并相邻高分窗口
        var sortedWindows = windows
            .OrderByDescending(w => w.Score)
            .ToList();

        var merged = new List<HighlightCandidate>();
        var used = new HashSet<int>();

        foreach (var w in sortedWindows)
        {
            if (used.Contains(w.Index) || merged.Count >= topN)
            {
                break;
            }

            // 尝试合并相邻窗口
            var mergeStart = w.Index;
            var mergeEnd = w.Index;

            // 向前合并
            while (mergeStart > 0 && !used.Contains(mergeStart - 1) &&
                   windows[mergeStart - 1].Score >= w.Score * 0.5)
            {
                mergeStart--;
            }

            // 向后合并
            while (mergeEnd < windowCount - 1 && !used.Contains(mergeEnd + 1) &&
                   windows[mergeEnd + 1].Score >= w.Score * 0.5)
            {
                mergeEnd++;
            }

            // 限制合并后最大时长为 30 秒
            var mergedDuration = (mergeEnd - mergeStart + 1) * windowSeconds;
            if (mergedDuration > 30.0)
            {
                mergeStart = w.Index;
                mergeEnd = w.Index;
            }

            for (var i = mergeStart; i <= mergeEnd; i++)
            {
                used.Add(i);
            }

            var startSec = windows[mergeStart].StartSeconds;
            var endSec = Math.Min(windows[mergeEnd].EndSeconds, totalDurationSeconds);

            var mergedWindows = windows.Skip(mergeStart).Take(mergeEnd - mergeStart + 1).ToList();
            var avgScore = mergedWindows.Average(mw => mw.Score);
            var avgSceneRate = mergedWindows.Average(mw => mw.SceneChangeRate);
            var avgVol = mergedWindows
                .Where(mw => mw.VolumeSamples.Count > 0)
                .Select(mw => mw.AverageVolume)
                .DefaultIfEmpty(double.NegativeInfinity)
                .Average();

            merged.Add(new HighlightCandidate
            {
                Rank = merged.Count + 1,
                StartSeconds = startSec,
                EndSeconds = endSec,
                DurationSeconds = endSec - startSec,
                Score = Math.Round(avgScore, 1),
                SceneChangeRate = Math.Round(avgSceneRate, 2),
                VolumeLevel = Math.Round(avgVol, 1),
                IsBlackFiltered = mergedWindows.Any(mw => mw.HasBlack),
                IsFreezeFiltered = mergedWindows.Any(mw => mw.HasFreeze)
            });
        }

        // 重新按 Score 排序并更新 Rank
        return merged
            .OrderByDescending(c => c.Score)
            .Select((c, i) => new HighlightCandidate
            {
                Rank = i + 1,
                StartSeconds = c.StartSeconds,
                EndSeconds = c.EndSeconds,
                DurationSeconds = c.DurationSeconds,
                Score = c.Score,
                SceneChangeRate = c.SceneChangeRate,
                VolumeLevel = c.VolumeLevel,
                IsBlackFiltered = c.IsBlackFiltered,
                IsFreezeFiltered = c.IsFreezeFiltered
            })
            .ToList();
    }

    private static void MarkOverlap(
        WindowData[] windows,
        double segStart,
        double segEnd,
        double windowSeconds,
        bool isBlack)
    {
        var startIndex = Math.Max((int)(segStart / windowSeconds), 0);
        var endIndex = Math.Min((int)(segEnd / windowSeconds), windows.Length - 1);

        for (var i = startIndex; i <= endIndex; i++)
        {
            if (isBlack)
            {
                windows[i].HasBlack = true;
            }
            else
            {
                windows[i].HasFreeze = true;
            }
        }
    }

    private sealed class WindowData
    {
        public int Index { get; init; }
        public double StartSeconds { get; init; }
        public double EndSeconds { get; init; }
        public double DurationSeconds { get; init; }
        public int SceneCutCount { get; set; }
        public List<double> VolumeSamples { get; } = [];
        public bool HasBlack { get; set; }
        public bool HasFreeze { get; set; }
        public double Score { get; set; }
        public double SceneChangeRate { get; set; }
        public double AverageVolume { get; set; }
    }
}
