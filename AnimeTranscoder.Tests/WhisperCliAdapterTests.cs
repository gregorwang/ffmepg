using System.Text;
using System.Reflection;
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
    public void BuildArguments_OmitsOffsetWhenVadIsEnabled()
    {
        var method = typeof(WhisperCliAdapter).GetMethod("BuildArguments", BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException("BuildArguments not found.");

        var arguments = (IReadOnlyList<string>)method.Invoke(null, [
            "input.wav",
            "model.bin",
            new WhisperOptions
            {
                Language = "en",
                ExtraArgs = "--vad -vm vad.bin -mc 0"
            },
            3600d
        ])!;

        Assert.DoesNotContain("-ot", arguments);
        Assert.Contains("--vad", arguments);
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

    [Fact]
    public async Task TranscribeAsync_ChunksLongAudioAndMergesSegments()
    {
        using var workspace = new TestWorkspace();
        var inputPath = workspace.CreateWaveFile("audio/input.wav", samples: new short[16000 * 3]);
        var modelPath = workspace.CreateTextFile("models/model.bin", "model");
        var invocationLogPath = workspace.PathFor("logs/chunk-invocations.txt");
        Directory.CreateDirectory(Path.GetDirectoryName(invocationLogPath)!);
        var executablePath = CreateChunkAwareWhisperExecutable(workspace, invocationLogPath);
        var adapter = CreateAdapter();

        var document = await adapter.TranscribeAsync(inputPath, new WhisperOptions
        {
            ExecutablePath = executablePath,
            ModelPath = modelPath,
            ChunkDurationSeconds = 1,
            ChunkOverlapSeconds = 0.2d,
            ResumePartialResults = true
        }, progress: null, CancellationToken.None);

        Assert.Collection(document.Segments,
            item =>
            {
                Assert.Equal("seg_001", item.Id);
                Assert.Equal("one", item.Text);
                Assert.Equal(0d, item.Start, 3);
                Assert.Equal(0.9d, item.End, 3);
            },
            item =>
            {
                Assert.Equal("seg_002", item.Id);
                Assert.Equal("two", item.Text);
                Assert.Equal(1.1d, item.Start, 3);
                Assert.Equal(1.7d, item.End, 3);
            },
            item =>
            {
                Assert.Equal("seg_003", item.Id);
                Assert.Equal("three", item.Text);
                Assert.Equal(2.05d, item.Start, 3);
                Assert.Equal(2.6d, item.End, 3);
            });

        var invocations = await File.ReadAllLinesAsync(invocationLogPath);
        Assert.Equal(3, invocations.Length);
    }

    [Fact]
    public async Task TranscribeAsync_ResumesFromChunkCacheWithoutReinvokingWhisper()
    {
        using var workspace = new TestWorkspace();
        var inputPath = workspace.CreateWaveFile("audio/input.wav", samples: new short[16000 * 3]);
        var modelPath = workspace.CreateTextFile("models/model.bin", "model");
        var warmupExecutable = CreateChunkAwareWhisperExecutable(workspace, workspace.PathFor("logs/warmup.txt"));
        var failLogPath = workspace.PathFor("logs/fail.txt");
        Directory.CreateDirectory(Path.GetDirectoryName(failLogPath)!);
        var failExecutable = CreateFailingWhisperExecutable(workspace, failLogPath);
        var adapter = CreateAdapter();
        var options = new WhisperOptions
        {
            ModelPath = modelPath,
            ChunkDurationSeconds = 1,
            ChunkOverlapSeconds = 0.2d,
            ResumePartialResults = true
        };

        await adapter.TranscribeAsync(inputPath, new WhisperOptions
        {
            ExecutablePath = warmupExecutable,
            ModelPath = options.ModelPath,
            ChunkDurationSeconds = options.ChunkDurationSeconds,
            ChunkOverlapSeconds = options.ChunkOverlapSeconds,
            ResumePartialResults = options.ResumePartialResults
        }, progress: null, CancellationToken.None);

        var resumed = await adapter.TranscribeAsync(inputPath, new WhisperOptions
        {
            ExecutablePath = failExecutable,
            ModelPath = options.ModelPath,
            ChunkDurationSeconds = options.ChunkDurationSeconds,
            ChunkOverlapSeconds = options.ChunkOverlapSeconds,
            ResumePartialResults = options.ResumePartialResults
        }, progress: null, CancellationToken.None);

        Assert.Equal(3, resumed.Segments.Count);
        Assert.False(File.Exists(failLogPath));
    }

    [Fact]
    public async Task TranscribeAsync_ChunksLongAudioWhenChunkJsonUsesRelativeTimestamps()
    {
        using var workspace = new TestWorkspace();
        var inputPath = workspace.CreateWaveFile("audio/input.wav", samples: new short[16000 * 3]);
        var modelPath = workspace.CreateTextFile("models/model.bin", "model");
        var executablePath = CreateRelativeChunkWhisperExecutable(workspace);
        var adapter = CreateAdapter();

        var document = await adapter.TranscribeAsync(inputPath, new WhisperOptions
        {
            ExecutablePath = executablePath,
            ModelPath = modelPath,
            ChunkDurationSeconds = 1,
            ChunkOverlapSeconds = 0.2d,
            ResumePartialResults = false
        }, progress: null, CancellationToken.None);

        Assert.Collection(
            document.Segments,
            first =>
            {
                Assert.Equal("one", first.Text);
                Assert.Equal(0d, first.Start, 3);
                Assert.Equal(0.9d, first.End, 3);
            },
            second =>
            {
                Assert.Equal("two", second.Text);
                Assert.Equal(1.1d, second.Start, 3);
                Assert.Equal(1.7d, second.End, 3);
            },
            third =>
            {
                Assert.Equal("three", third.Text);
                Assert.Equal(2.05d, third.Start, 3);
                Assert.Equal(2.6d, third.End, 3);
            });
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

    private static string CreateChunkAwareWhisperExecutable(TestWorkspace workspace, string invocationLogPath)
    {
        var ps1Path = workspace.PathFor("tools/chunk-whisper.ps1");
        var cmdPath = workspace.PathFor("tools/chunk-whisper.cmd");
        Directory.CreateDirectory(Path.GetDirectoryName(ps1Path)!);
        var script = $@"$ErrorActionPreference = 'Stop'
$inputPath = ''
$offsetMs = 0
for ($i = 0; $i -lt $args.Length; $i++) {{
    if ($args[$i] -eq '-f' -and $i + 1 -lt $args.Length) {{
        $inputPath = $args[$i + 1]
    }}
    elseif ($args[$i] -eq '-ot' -and $i + 1 -lt $args.Length) {{
        $offsetMs = [int]$args[$i + 1]
    }}
}}
[System.IO.File]::AppendAllText('{invocationLogPath.Replace("'", "''")}', (Split-Path $inputPath -Leaf) + [Environment]::NewLine, [System.Text.Encoding]::UTF8)
$leaf = Split-Path $inputPath -Leaf
switch ($leaf) {{
    'chunk-0001.wav' {{ $items = @(@{{ offsets = @{{ from = 0; to = 900 }}; text = ' one' }}) }}
    'chunk-0002.wav' {{ $items = @(@{{ offsets = @{{ from = 0; to = 300 }}; text = ' one' }}, @{{ offsets = @{{ from = 300; to = 900 }}; text = ' two' }}) }}
    'chunk-0003.wav' {{ $items = @(@{{ offsets = @{{ from = 0; to = 250 }}; text = ' two' }}, @{{ offsets = @{{ from = 250; to = 800 }}; text = ' three' }}) }}
    default {{ throw ""unexpected chunk file: $leaf"" }}
}}
foreach ($item in $items) {{
    $item.offsets.from += $offsetMs
    $item.offsets.to += $offsetMs
}}
$json = @{{ transcription = $items }} | ConvertTo-Json -Depth 5 -Compress
[System.IO.File]::WriteAllText($inputPath + '.json', $json, [System.Text.Encoding]::UTF8)
[Console]::Error.WriteLine('50%')
exit 0
";
        File.WriteAllText(ps1Path, script, Encoding.UTF8);
        File.WriteAllText(cmdPath, "@echo off" + Environment.NewLine +
            "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0chunk-whisper.ps1\" %*" + Environment.NewLine +
            "exit /b %errorlevel%" + Environment.NewLine, Encoding.ASCII);
        return cmdPath;
    }

    private static string CreateFailingWhisperExecutable(TestWorkspace workspace, string invocationLogPath)
    {
        var ps1Path = workspace.PathFor("tools/fail-whisper.ps1");
        var cmdPath = workspace.PathFor("tools/fail-whisper.cmd");
        Directory.CreateDirectory(Path.GetDirectoryName(ps1Path)!);
        var script = $@"$ErrorActionPreference = 'Stop'
[System.IO.File]::AppendAllText('{invocationLogPath.Replace("'", "''")}', 'invoked' + [Environment]::NewLine, [System.Text.Encoding]::UTF8)
[Console]::Error.WriteLine('should not run')
exit 9
";
        File.WriteAllText(ps1Path, script, Encoding.UTF8);
        File.WriteAllText(cmdPath, "@echo off" + Environment.NewLine +
            "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0fail-whisper.ps1\" %*" + Environment.NewLine +
            "exit /b %errorlevel%" + Environment.NewLine, Encoding.ASCII);
        return cmdPath;
    }

    private static string CreateRelativeChunkWhisperExecutable(TestWorkspace workspace)
    {
        var ps1Path = workspace.PathFor("tools/relative-chunk-whisper.ps1");
        var cmdPath = workspace.PathFor("tools/relative-chunk-whisper.cmd");
        Directory.CreateDirectory(Path.GetDirectoryName(ps1Path)!);
        var script = @"$ErrorActionPreference = 'Stop'
$inputPath = ''
for ($i = 0; $i -lt $args.Length; $i++) {
    if ($args[$i] -eq '-f' -and $i + 1 -lt $args.Length) {
        $inputPath = $args[$i + 1]
    }
}
$leaf = Split-Path $inputPath -Leaf
switch ($leaf) {
    'chunk-0001.wav' { $items = @(@{ offsets = @{ from = 0; to = 900 }; text = ' one' }) }
    'chunk-0002.wav' { $items = @(@{ offsets = @{ from = 300; to = 900 }; text = ' two' }) }
    'chunk-0003.wav' { $items = @(@{ offsets = @{ from = 250; to = 800 }; text = ' three' }) }
    default { throw ""unexpected chunk file: $leaf"" }
}
$json = @{ transcription = $items } | ConvertTo-Json -Depth 5 -Compress
[System.IO.File]::WriteAllText($inputPath + '.json', $json, [System.Text.Encoding]::UTF8)
[Console]::Error.WriteLine('50%')
exit 0
";
        File.WriteAllText(ps1Path, script, Encoding.UTF8);
        File.WriteAllText(cmdPath, "@echo off" + Environment.NewLine +
            "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0relative-chunk-whisper.ps1\" %*" + Environment.NewLine +
            "exit /b %errorlevel%" + Environment.NewLine, Encoding.ASCII);
        return cmdPath;
    }
}
