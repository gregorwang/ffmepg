using System.Text;
using AnimeTranscoder.Models;
using AnimeTranscoder.Services;
using Xunit;

namespace AnimeTranscoder.Tests;

public sealed class WhisperCliAdapterTests
{
    [Fact]
    public async Task TranscribeAsync_BuildsExpectedCommandLineArguments()
    {
        using var workspace = new TestWorkspace();
        var inputPath = workspace.CreateWaveFile("audio/input.wav");
        var modelPath = workspace.CreateTextFile("models/model.bin", "model");
        var argsPath = workspace.PathFor("logs/args.txt");
        Directory.CreateDirectory(Path.GetDirectoryName(argsPath)!);
        var executablePath = CreateFakeWhisperExecutable(workspace, """{"transcription":[]}""", argsPath, "25%");
        var adapter = CreateAdapter();

        await adapter.TranscribeAsync(inputPath, new WhisperOptions
        {
            ExecutablePath = executablePath,
            ModelPath = modelPath,
            Language = "ja",
            Threads = 4,
            ExtraArgs = "--temperature 0.2 --best_of 3"
        }, progress: null, CancellationToken.None);

        var arguments = await File.ReadAllTextAsync(argsPath);
        Assert.Contains("-m", arguments);
        Assert.Contains(Path.GetFullPath(modelPath), arguments);
        Assert.Contains("-f", arguments);
        Assert.Contains(Path.GetFileName(inputPath), arguments);
        Assert.Contains("-oj", arguments);
        Assert.Contains("-l ja", arguments);
        Assert.Contains("-t 4", arguments);
        Assert.Contains("--temperature 0.2", arguments);
        Assert.Contains("--best_of 3", arguments);
    }

    [Fact]
    public async Task TranscribeAsync_ParsesWhisperJsonIntoTranscriptDocument()
    {
        using var workspace = new TestWorkspace();
        var inputPath = workspace.CreateWaveFile("audio/input.wav");
        var modelPath = workspace.CreateTextFile("models/model.bin", "model");
        var executablePath = CreateFakeWhisperExecutable(workspace, """
{"transcription":[{"offsets":{"from":0,"to":1250},"text":" hello"},{"offsets":{"from":1250,"to":2500},"text":" world"}]}
""");
        var adapter = CreateAdapter();

        var document = await adapter.TranscribeAsync(inputPath, new WhisperOptions
        {
            ExecutablePath = executablePath,
            ModelPath = modelPath
        }, progress: null, CancellationToken.None);

        Assert.Equal(Path.GetFullPath(inputPath), document.AudioPath);
        Assert.Collection(document.Segments,
            item =>
            {
                Assert.Equal("seg_001", item.Id);
                Assert.Equal(0d, item.Start, 3);
                Assert.Equal(1.25d, item.End, 3);
                Assert.Equal("hello", item.Text);
            },
            item =>
            {
                Assert.Equal("seg_002", item.Id);
                Assert.Equal(1.25d, item.Start, 3);
                Assert.Equal(2.5d, item.End, 3);
                Assert.Equal("world", item.Text);
            });
    }

    [Fact]
    public async Task TranscribeAsync_HandlesEmptyTranscriptionResult()
    {
        using var workspace = new TestWorkspace();
        var inputPath = workspace.CreateWaveFile("audio/input.wav");
        var modelPath = workspace.CreateTextFile("models/model.bin", "model");
        var executablePath = CreateFakeWhisperExecutable(workspace, """{"transcription":[]}""");
        var adapter = CreateAdapter();

        var document = await adapter.TranscribeAsync(inputPath, new WhisperOptions
        {
            ExecutablePath = executablePath,
            ModelPath = modelPath
        }, progress: null, CancellationToken.None);

        Assert.Empty(document.Segments);
    }

    [Fact]
    public async Task TranscribeAsync_HandlesZeroDurationSegments()
    {
        using var workspace = new TestWorkspace();
        var inputPath = workspace.CreateWaveFile("audio/input.wav");
        var modelPath = workspace.CreateTextFile("models/model.bin", "model");
        var executablePath = CreateFakeWhisperExecutable(workspace, """
{"transcription":[{"offsets":{"from":2000,"to":2000},"text":" zero"}]}
""");
        var adapter = CreateAdapter();

        var document = await adapter.TranscribeAsync(inputPath, new WhisperOptions
        {
            ExecutablePath = executablePath,
            ModelPath = modelPath
        }, progress: null, CancellationToken.None);

        var segment = Assert.Single(document.Segments);
        Assert.Equal(2d, segment.Start, 3);
        Assert.Equal(2d, segment.End, 3);
        Assert.Equal("zero", segment.Text);
    }

    [Fact]
    public async Task TranscribeAsync_HandlesUnicodeText()
    {
        using var workspace = new TestWorkspace();
        var inputPath = workspace.CreateWaveFile("audio/input.wav");
        var modelPath = workspace.CreateTextFile("models/model.bin", "model");
        var executablePath = CreateFakeWhisperExecutable(workspace, """
{"transcription":[{"offsets":{"from":0,"to":500},"text":" 你好，世界"}]}
""");
        var adapter = CreateAdapter();

        var document = await adapter.TranscribeAsync(inputPath, new WhisperOptions
        {
            ExecutablePath = executablePath,
            ModelPath = modelPath
        }, progress: null, CancellationToken.None);

        var segment = Assert.Single(document.Segments);
        Assert.Equal("你好，世界", segment.Text);
    }

    [Fact]
    public async Task TranscribeAsync_ReportsProgressFromStderr()
    {
        using var workspace = new TestWorkspace();
        var inputPath = workspace.CreateWaveFile("audio/input.wav");
        var modelPath = workspace.CreateTextFile("models/model.bin", "model");
        var executablePath = CreateFakeWhisperExecutable(workspace, """{"transcription":[]}""", stderrText: "49%");
        var adapter = CreateAdapter();
        var progressValues = new List<double>();

        await adapter.TranscribeAsync(inputPath, new WhisperOptions
        {
            ExecutablePath = executablePath,
            ModelPath = modelPath
        }, new Progress<double>(progressValues.Add), CancellationToken.None);

        Assert.Contains(progressValues, value => Math.Abs(value - 49d) < 0.001);
    }

    [Fact]
    public async Task TranscribeAsync_ThrowsWhenExecutableDoesNotExist()
    {
        using var workspace = new TestWorkspace();
        var inputPath = workspace.CreateWaveFile("audio/input.wav");
        var modelPath = workspace.CreateTextFile("models/model.bin", "model");
        var adapter = CreateAdapter();

        await Assert.ThrowsAsync<FileNotFoundException>(() =>
            adapter.TranscribeAsync(inputPath, new WhisperOptions
            {
                ExecutablePath = workspace.PathFor("missing/fake.exe"),
                ModelPath = modelPath
            }, progress: null, CancellationToken.None));
    }

    [Fact]
    public async Task TranscribeAsync_ThrowsWhenModelDoesNotExist()
    {
        using var workspace = new TestWorkspace();
        var inputPath = workspace.CreateWaveFile("audio/input.wav");
        var executablePath = CreateFakeWhisperExecutable(workspace, """{"transcription":[]}""");
        var adapter = CreateAdapter();

        await Assert.ThrowsAsync<FileNotFoundException>(() =>
            adapter.TranscribeAsync(inputPath, new WhisperOptions
            {
                ExecutablePath = executablePath,
                ModelPath = workspace.PathFor("models/missing.bin")
            }, progress: null, CancellationToken.None));
    }

    [Fact]
    public async Task TranscribeAsync_CleansUpIntermediateJsonFile()
    {
        using var workspace = new TestWorkspace();
        var inputPath = workspace.CreateWaveFile("audio/input.wav");
        var modelPath = workspace.CreateTextFile("models/model.bin", "model");
        var executablePath = CreateFakeWhisperExecutable(workspace, """{"transcription":[]}""");
        var adapter = CreateAdapter();

        await adapter.TranscribeAsync(inputPath, new WhisperOptions
        {
            ExecutablePath = executablePath,
            ModelPath = modelPath
        }, progress: null, CancellationToken.None);

        Assert.False(File.Exists(inputPath + ".json"));
    }

    private static WhisperCliAdapter CreateAdapter()
    {
        return new WhisperCliAdapter(new AudioExtractionService(new FfmpegRunner(new FfmpegCommandBuilder()), new AudioCommandBuilder()));
    }

    private static string CreateFakeWhisperExecutable(TestWorkspace workspace, string outputJson, string? argsCapturePath = null, string stderrText = "50%")
    {
        var ps1Path = workspace.PathFor("tools/fake-whisper.ps1");
        var cmdPath = workspace.PathFor("tools/fake-whisper.cmd");
        Directory.CreateDirectory(Path.GetDirectoryName(ps1Path)!);
        var argsCapture = argsCapturePath is null ? "$null" : $"'{argsCapturePath.Replace("'", "''")}'";
        var script = $@"$ErrorActionPreference = 'Stop'
$inputPath = ''
$capturePath = {argsCapture}
if ($capturePath) {{
    [System.IO.File]::WriteAllText($capturePath, ($args -join ' '), [System.Text.Encoding]::UTF8)
}}
for ($i = 0; $i -lt $args.Length; $i++) {{
    if ($args[$i] -eq '-f' -and $i + 1 -lt $args.Length) {{
        $inputPath = $args[$i + 1]
    }}
}}
[Console]::Error.WriteLine('{stderrText.Replace("'", "''")}')
[System.IO.File]::WriteAllText($inputPath + '.json', @'
{outputJson}
'@, [System.Text.Encoding]::UTF8)
exit 0
";
        File.WriteAllText(ps1Path, script, Encoding.UTF8);
        File.WriteAllText(cmdPath, "@echo off" + Environment.NewLine +
            "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0fake-whisper.ps1\" %*" + Environment.NewLine +
            "exit /b %errorlevel%" + Environment.NewLine, Encoding.ASCII);
        return cmdPath;
    }
}
