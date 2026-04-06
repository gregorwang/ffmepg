using System.Text.Json;
using AnimeTranscoder.Infrastructure;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class JsonSettingsService
{
    private readonly JsonSerializerOptions _jsonOptions = new() { WriteIndented = true };

    public string SettingsPath { get; }

    public JsonSettingsService()
    {
        var appDirectory = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "AnimeTranscoder");

        Directory.CreateDirectory(appDirectory);
        SettingsPath = Path.Combine(appDirectory, "settings.json");
    }

    public async Task<AppSettings> LoadAsync()
    {
        var defaults = AppSettings.CreateDefault(ToolPathResolver.ResolveWorkspaceRoot());

        if (!File.Exists(SettingsPath))
        {
            return defaults;
        }

        var json = await File.ReadAllTextAsync(SettingsPath);
        var settings = JsonSerializer.Deserialize<AppSettings>(json, _jsonOptions);
        if (settings is null)
        {
            return defaults;
        }

        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;

        settings.InputDirectory = string.IsNullOrWhiteSpace(settings.InputDirectory) ? defaults.InputDirectory : settings.InputDirectory;
        settings.OutputDirectory = string.IsNullOrWhiteSpace(settings.OutputDirectory) ? defaults.OutputDirectory : settings.OutputDirectory;
        settings.SubtitlePreference = string.IsNullOrWhiteSpace(settings.SubtitlePreference) ? defaults.SubtitlePreference : settings.SubtitlePreference;
        settings.VideoEncoderMode = string.IsNullOrWhiteSpace(settings.VideoEncoderMode) ? defaults.VideoEncoderMode : settings.VideoEncoderMode;
        settings.NvencPreset = string.IsNullOrWhiteSpace(settings.NvencPreset) ? defaults.NvencPreset : settings.NvencPreset;
        settings.Cq = settings.Cq <= 0 ? defaults.Cq : settings.Cq;
        settings.AudioBitrateKbps = settings.AudioBitrateKbps <= 0 ? defaults.AudioBitrateKbps : settings.AudioBitrateKbps;
        settings.StableFileWaitSeconds = settings.StableFileWaitSeconds <= 0 ? defaults.StableFileWaitSeconds : settings.StableFileWaitSeconds;
        settings.OutputSafetyMarginMb = settings.OutputSafetyMarginMb <= 0 ? defaults.OutputSafetyMarginMb : settings.OutputSafetyMarginMb;

        if (!root.TryGetProperty(nameof(AppSettings.EnableDirectoryWatch), out _))
        {
            settings.EnableDirectoryWatch = defaults.EnableDirectoryWatch;
        }

        if (!root.TryGetProperty(nameof(AppSettings.AutoStartQueueOnWatch), out _))
        {
            settings.AutoStartQueueOnWatch = defaults.AutoStartQueueOnWatch;
        }

        if (!root.TryGetProperty(nameof(AppSettings.PreferStereoAudio), out _))
        {
            settings.PreferStereoAudio = defaults.PreferStereoAudio;
        }

        if (!root.TryGetProperty(nameof(AppSettings.EnableFaststart), out _))
        {
            settings.EnableFaststart = defaults.EnableFaststart;
        }

        return settings;
    }

    public async Task SaveAsync(AppSettings settings)
    {
        await using var stream = File.Create(SettingsPath);
        await JsonSerializer.SerializeAsync(stream, settings, _jsonOptions);
    }
}
