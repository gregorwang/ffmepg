namespace AnimeTranscoder.Models;

public sealed class TranscodeQueueExecutionResult
{
    public bool QueueWasCancelled { get; init; }
    public IReadOnlyList<TranscodeTaskResult> TaskResults { get; init; } = [];
}
