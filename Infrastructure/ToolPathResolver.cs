namespace AnimeTranscoder.Infrastructure;

public static class ToolPathResolver
{
    public static string ResolveWorkspaceRoot()
    {
        var current = new DirectoryInfo(AppContext.BaseDirectory);

        while (current is not null)
        {
            if (File.Exists(Path.Combine(current.FullName, "convert_hardsub_mp4.ps1")) ||
                Directory.Exists(Path.Combine(current.FullName, "mp4_hardsub_chs")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        return Environment.GetFolderPath(Environment.SpecialFolder.MyVideos);
    }

    public static string ResolveFfmpegPath() => ResolveToolPath("ffmpeg.exe", "ffmpeg");

    public static string ResolveFfprobePath() => ResolveToolPath("ffprobe.exe", "ffprobe");

    private static string ResolveToolPath(string executableName, string fallbackCommand)
    {
        var current = new DirectoryInfo(AppContext.BaseDirectory);

        while (current is not null)
        {
            var candidate = Path.Combine(current.FullName, "tools", "ffmpeg", executableName);
            if (File.Exists(candidate))
            {
                return candidate;
            }

            current = current.Parent;
        }

        return fallbackCommand;
    }
}
