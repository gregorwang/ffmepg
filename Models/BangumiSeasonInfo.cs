namespace AnimeTranscoder.Models;

public sealed class BangumiSeasonInfo
{
    public int SeasonId { get; init; }
    public string Title { get; init; } = string.Empty;
    public string OriginalTitle { get; init; } = string.Empty;
    public string SeriesTitle { get; init; } = string.Empty;
    public string Url { get; init; } = string.Empty;
    public string SeasonTypeName { get; init; } = string.Empty;
    public int EpisodeCount { get; init; }
    public List<BangumiEpisodeInfo> Episodes { get; init; } = [];
}

public sealed class BangumiEpisodeInfo
{
    public int EpisodeId { get; init; }
    public long Cid { get; init; }
    public int Number { get; init; }
    public string Title { get; init; } = string.Empty;
    public string LongTitle { get; init; } = string.Empty;
    public string ShowTitle { get; init; } = string.Empty;
    public string ShareCopy { get; init; } = string.Empty;
    public int SectionType { get; init; }
}
