using System.Text;

namespace AnimeTranscoder.Infrastructure;

public static class AppFileLogger
{
    private static readonly object SyncRoot = new();
    private static readonly string InternalLogDirectory;

    static AppFileLogger()
    {
        InternalLogDirectory = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "AnimeTranscoder",
            "logs");

        Directory.CreateDirectory(InternalLogDirectory);
    }

    public static string LogDirectory => InternalLogDirectory;

    public static string CurrentLogPath => Path.Combine(InternalLogDirectory, $"AnimeTranscoder-{DateTime.Now:yyyyMMdd}.log");

    public static void Write(string source, string message)
    {
        if (string.IsNullOrWhiteSpace(message))
        {
            return;
        }

        var line = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}] [{source}] {message}";

        lock (SyncRoot)
        {
            File.AppendAllText(CurrentLogPath, line + Environment.NewLine, Encoding.UTF8);
        }
    }

    public static void WriteException(string source, Exception exception)
    {
        Write(source, exception.ToString());
    }
}
