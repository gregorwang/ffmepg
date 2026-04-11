using AnimeTranscoder.Models;
using AnimeTranscoder.Services;

namespace AnimeTranscoder.Workflows;

public sealed class MediaProbeWorkflow
{
    private readonly FfprobeService _ffprobeService;

    public MediaProbeWorkflow(FfprobeService ffprobeService)
    {
        _ffprobeService = ffprobeService;
    }

    public async Task<MediaProbeResult> ProbeAsync(string inputPath, CancellationToken cancellationToken)
    {
        var result = await _ffprobeService.ProbeAsync(inputPath, cancellationToken);
        return result ?? throw new InvalidOperationException("媒体探测未返回结果。");
    }
}
