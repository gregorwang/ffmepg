namespace AnimeTranscoder.Models;

public sealed class WhisperOptions
{
    public string ExecutablePath { get; set; } = "main";
    public string ModelPath { get; set; } = string.Empty;
    public string Language { get; set; } = "auto";
    public int Threads { get; set; }
    public string ExtraArgs { get; set; } = string.Empty;
    public int ChunkDurationSeconds { get; set; } = 1800;
    public double ChunkOverlapSeconds { get; set; } = 2d;
    public bool ResumePartialResults { get; set; } = true;
}
