namespace AnimeTranscoder.Models;

public sealed class AnimeEpisodeMatch
{
    public string InputFileName { get; init; } = string.Empty;
    public string RawTitle { get; init; } = string.Empty;
    public string NormalizedTitle { get; init; } = string.Empty;
    public string SearchKeyword { get; init; } = string.Empty;
    public int EpisodeNumber { get; init; }
    public int? SeasonNumber { get; init; }
    public string EpisodeToken { get; init; } = string.Empty;
}
