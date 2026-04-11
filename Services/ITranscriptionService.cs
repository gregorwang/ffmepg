using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public interface ITranscriptionService
{
    Task<TranscriptDocument> TranscribeAsync(
        string audioFilePath,
        WhisperOptions options,
        IProgress<double>? progress,
        CancellationToken cancellationToken);
}
