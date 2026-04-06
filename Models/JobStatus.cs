namespace AnimeTranscoder.Models;

public enum JobStatus
{
    Pending,
    Probing,
    Ready,
    Running,
    Success,
    Failed,
    Skipped,
    Cancelled
}
