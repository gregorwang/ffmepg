using System.Collections.Concurrent;

namespace AnimeTranscoder.Services;

public sealed class DirectoryWatchService : IDisposable
{
    private readonly ConcurrentDictionary<string, CancellationTokenSource> _pendingChecks = new(StringComparer.OrdinalIgnoreCase);
    private FileSystemWatcher? _watcher;
    private Action<string>? _onStableFileReady;
    private Action<string>? _logCallback;
    private int _stableWaitSeconds = 20;

    public bool IsRunning => _watcher is not null;

    public void Start(
        string directoryPath,
        int stableWaitSeconds,
        Action<string> onStableFileReady,
        Action<string> logCallback)
    {
        Stop();

        if (string.IsNullOrWhiteSpace(directoryPath) || !Directory.Exists(directoryPath))
        {
            logCallback("目录监听未启动：输入目录不存在。");
            return;
        }

        _stableWaitSeconds = Math.Max(5, stableWaitSeconds);
        _onStableFileReady = onStableFileReady;
        _logCallback = logCallback;

        _watcher = new FileSystemWatcher(directoryPath, "*.mkv")
        {
            IncludeSubdirectories = false,
            NotifyFilter = NotifyFilters.FileName | NotifyFilters.LastWrite | NotifyFilters.Size,
            EnableRaisingEvents = true
        };

        _watcher.Created += OnFileChanged;
        _watcher.Changed += OnFileChanged;
        _watcher.Renamed += OnFileRenamed;
        _watcher.Error += OnWatcherError;

        _logCallback($"目录监听已启动：{directoryPath}，稳定检测等待 {_stableWaitSeconds} 秒。");
    }

    public void Stop()
    {
        foreach (var pair in _pendingChecks)
        {
            pair.Value.Cancel();
            pair.Value.Dispose();
        }

        _pendingChecks.Clear();

        if (_watcher is null)
        {
            return;
        }

        _watcher.EnableRaisingEvents = false;
        _watcher.Created -= OnFileChanged;
        _watcher.Changed -= OnFileChanged;
        _watcher.Renamed -= OnFileRenamed;
        _watcher.Error -= OnWatcherError;
        _watcher.Dispose();
        _watcher = null;

        _logCallback?.Invoke("目录监听已停止。");
    }

    private void OnFileChanged(object sender, FileSystemEventArgs e)
    {
        ScheduleStabilityCheck(e.FullPath);
    }

    private void OnFileRenamed(object sender, RenamedEventArgs e)
    {
        ScheduleStabilityCheck(e.FullPath);
    }

    private void OnWatcherError(object sender, ErrorEventArgs e)
    {
        _logCallback?.Invoke($"目录监听异常：{e.GetException().Message}");
    }

    private void ScheduleStabilityCheck(string path)
    {
        if (!path.EndsWith(".mkv", StringComparison.OrdinalIgnoreCase))
        {
            return;
        }

        if (_pendingChecks.TryRemove(path, out var existing))
        {
            existing.Cancel();
            existing.Dispose();
        }

        var cts = new CancellationTokenSource();
        _pendingChecks[path] = cts;
        _ = WaitForStableFileAsync(path, cts.Token);
    }

    private async Task WaitForStableFileAsync(string path, CancellationToken cancellationToken)
    {
        try
        {
            await Task.Delay(TimeSpan.FromSeconds(_stableWaitSeconds), cancellationToken);

            FileSnapshot? previous = null;

            for (var attempt = 0; attempt < 6; attempt++)
            {
                cancellationToken.ThrowIfCancellationRequested();

                var current = TryReadSnapshot(path);
                if (current is null)
                {
                    await Task.Delay(TimeSpan.FromSeconds(2), cancellationToken);
                    continue;
                }

                if (previous is not null &&
                    previous.Length == current.Length &&
                    previous.LastWriteTimeUtc == current.LastWriteTimeUtc &&
                    CanOpenForRead(path))
                {
                    _logCallback?.Invoke($"检测到稳定文件，已自动加入队列：{Path.GetFileName(path)}");
                    _onStableFileReady?.Invoke(path);
                    return;
                }

                previous = current;
                await Task.Delay(TimeSpan.FromSeconds(2), cancellationToken);
            }

            _logCallback?.Invoke($"文件稳定检测超时，已放弃自动入队：{Path.GetFileName(path)}");
        }
        catch (OperationCanceledException)
        {
        }
        finally
        {
            if (_pendingChecks.TryRemove(path, out var cts))
            {
                cts.Dispose();
            }
        }
    }

    private static FileSnapshot? TryReadSnapshot(string path)
    {
        try
        {
            var info = new FileInfo(path);
            if (!info.Exists)
            {
                return null;
            }

            return new FileSnapshot(info.Length, info.LastWriteTimeUtc);
        }
        catch
        {
            return null;
        }
    }

    private static bool CanOpenForRead(string path)
    {
        try
        {
            using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
            return stream.Length >= 0;
        }
        catch
        {
            return false;
        }
    }

    public void Dispose()
    {
        Stop();
    }

    private sealed record FileSnapshot(long Length, DateTime LastWriteTimeUtc);
}
