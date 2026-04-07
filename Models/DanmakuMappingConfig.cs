namespace AnimeTranscoder.Models;

public sealed class DanmakuMappingConfig
{
    public List<DanmakuTitleMappingEntry> Mappings { get; init; } = [];
}

public sealed class DanmakuTitleMappingEntry
{
    public string Name { get; init; } = string.Empty;
    public string SearchKeyword { get; init; } = string.Empty;
    public int? SeasonId { get; init; }
    public List<string> LocalTitles { get; init; } = [];
    public List<DanmakuEpisodeOverride> EpisodeOverrides { get; init; } = [];
}

public sealed class DanmakuEpisodeOverride
{
    public int EpisodeNumber { get; init; }
    public long? Cid { get; init; }
    public int? EpisodeId { get; init; }
    public string TitleContains { get; init; } = string.Empty;
}
