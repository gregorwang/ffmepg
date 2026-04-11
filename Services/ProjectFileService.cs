using System.Text.Json;
using AnimeTranscoder.Models;

namespace AnimeTranscoder.Services;

public sealed class ProjectFileService
{
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        WriteIndented = true
    };

    public AnimeProjectFile Create(string inputPath, string projectPath)
    {
        if (string.IsNullOrWhiteSpace(inputPath))
        {
            throw new ArgumentException("输入文件不能为空。", nameof(inputPath));
        }

        var absoluteInputPath = Path.GetFullPath(inputPath);
        if (!File.Exists(absoluteInputPath))
        {
            throw new FileNotFoundException("输入文件不存在。", absoluteInputPath);
        }

        var absoluteProjectPath = Path.GetFullPath(projectPath);
        var projectDirectory = Path.GetDirectoryName(absoluteProjectPath)
            ?? throw new InvalidOperationException("项目文件目录无效。");
        var projectName = Path.GetFileNameWithoutExtension(absoluteProjectPath);
        var workingDirectory = Path.Combine(projectDirectory, $"{projectName}.artifacts");

        Directory.CreateDirectory(projectDirectory);
        Directory.CreateDirectory(workingDirectory);

        return new AnimeProjectFile
        {
            InputPath = absoluteInputPath,
            WorkingDirectory = workingDirectory,
            Status = "initialized"
        };
    }

    public async Task<AnimeProjectFile> LoadAsync(string projectPath, CancellationToken cancellationToken = default)
    {
        var absoluteProjectPath = Path.GetFullPath(projectPath);
        if (!File.Exists(absoluteProjectPath))
        {
            throw new FileNotFoundException("项目文件不存在。", absoluteProjectPath);
        }

        AnimeProjectFile? project;
        await using var stream = File.OpenRead(absoluteProjectPath);
        try
        {
            project = await JsonSerializer.DeserializeAsync<AnimeProjectFile>(stream, _jsonOptions, cancellationToken);
        }
        catch (JsonException ex)
        {
            throw new InvalidOperationException("项目文件解析失败：JSON 格式无效。", ex);
        }

        if (project is null)
        {
            throw new InvalidOperationException("项目文件解析失败。");
        }

        Normalize(project);
        Validate(project);
        return project;
    }

    public async Task SaveAsync(string projectPath, AnimeProjectFile project, CancellationToken cancellationToken = default)
    {
        Normalize(project);
        Validate(project);
        project.UpdatedAtUtc = DateTime.UtcNow;

        var absoluteProjectPath = Path.GetFullPath(projectPath);
        var directory = Path.GetDirectoryName(absoluteProjectPath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        await using var stream = File.Create(absoluteProjectPath);
        await JsonSerializer.SerializeAsync(stream, project, _jsonOptions, cancellationToken);
    }

    private static void Normalize(AnimeProjectFile project)
    {
        project.InputPath = NormalizePath(project.InputPath);
        project.WorkingDirectory = NormalizePath(project.WorkingDirectory);
        project.WorkingAudioPath = NormalizePath(project.WorkingAudioPath);
        project.TranscriptPath = NormalizePath(project.TranscriptPath);
        project.SelectionPath = NormalizePath(project.SelectionPath);
    }

    private static void Validate(AnimeProjectFile project)
    {
        if (string.IsNullOrWhiteSpace(project.InputPath))
        {
            throw new InvalidOperationException("项目文件缺少 InputPath。");
        }

        if (string.IsNullOrWhiteSpace(project.WorkingDirectory))
        {
            throw new InvalidOperationException("项目文件缺少 WorkingDirectory。");
        }
    }

    private static string NormalizePath(string path)
    {
        return string.IsNullOrWhiteSpace(path)
            ? string.Empty
            : Path.GetFullPath(path);
    }
}
