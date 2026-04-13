using System.Reflection;
using AnimeTranscoder.Models;
using Xunit;

namespace AnimeTranscoder.Tests;

public sealed class CliProgramTests
{
    [Fact]
    public void ParseOptions_ProbeInputParsesRequiredValue()
    {
        var options = InvokePrivateStatic<Dictionary<string, string?>>("ParseOptions", (object)new[] { "--input", "demo.mp4" });

        Assert.Equal("demo.mp4", options["input"]);
    }

    [Fact]
    public void ParseOptions_AudioExportWorkParsesAllFlags()
    {
        var options = InvokePrivateStatic<Dictionary<string, string?>>("ParseOptions", (object)new[] { "--project", "demo.atproj", "--track", "2", "--sample-rate", "22050", "--progress", "jsonl" });

        Assert.Equal("demo.atproj", options["project"]);
        Assert.Equal("2", options["track"]);
        Assert.Equal("22050", options["sample-rate"]);
        Assert.Equal("jsonl", options["progress"]);
    }

    [Fact]
    public void ParseOptions_TranscriptGenerateParsesChunkingFlags()
    {
        var options = InvokePrivateStatic<Dictionary<string, string?>>("ParseOptions", (object)new[]
        {
            "--project", "demo.atproj",
            "--chunk-duration", "1200",
            "--chunk-overlap", "3.5",
            "--resume-partials", "false"
        });

        Assert.Equal("demo.atproj", options["project"]);
        Assert.Equal("1200", options["chunk-duration"]);
        Assert.Equal("3.5", options["chunk-overlap"]);
        Assert.Equal("false", options["resume-partials"]);
    }

    [Fact]
    public async Task Main_MissingRequiredArgumentReturnsValidationError()
    {
        var exitCode = await InvokeMainAsync(["probe"]);

        Assert.Equal(1, exitCode);
    }

    [Fact]
    public async Task Main_UnknownFlagReturnsValidationError()
    {
        var exitCode = await InvokeMainAsync(["probe", "--unknown", "x"]);

        Assert.Equal(1, exitCode);
    }

    [Fact]
    public async Task Main_HelpReturnsSuccess()
    {
        var exitCode = await InvokeMainAsync(["--help"]);

        Assert.Equal(0, exitCode);
    }

    [Fact]
    public async Task LoadTranscodeTasksAsync_ValidSpecDeserializesTasks()
    {
        using var workspace = new TestWorkspace();
        var specPath = workspace.CreateTextFile("queue/spec.json", """
{
  "tasks": [
    {
      "input": "C:/videos/raw1.mp4",
      "output": "C:/videos/out1.mp4",
      "preset": "default",
      "deleteSource": true,
      "noOverlay": true
    }
  ]
}
""");

        var tasks = await InvokePrivateStaticAsync<IReadOnlyList<TranscodeTaskSpec>>("LoadTranscodeTasksAsync", specPath, CancellationToken.None);

        var task = Assert.Single(tasks);
        Assert.Equal("C:/videos/raw1.mp4", task.InputPath);
        Assert.Equal("C:/videos/out1.mp4", task.OutputPath);
        Assert.Equal("default", task.Preset);
        Assert.True(task.DeleteSource.HasValue && task.DeleteSource.Value);
        Assert.True(task.NoOverlay);
    }

    [Fact]
    public void ParseOptions_TranscodeRunParsesAllFlags()
    {
        var options = InvokePrivateStatic<Dictionary<string, string?>>(
            "ParseOptions",
            (object)new[] { "--input", "in.mp4", "--output", "out.mp4", "--preset", "default", "--no-overlay", "--progress", "jsonl" });

        Assert.Equal("in.mp4", options["input"]);
        Assert.Equal("out.mp4", options["output"]);
        Assert.Equal("default", options["preset"]);
        Assert.Equal("true", options["no-overlay"]);
        Assert.Equal("jsonl", options["progress"]);
    }

    [Fact]
    public void ParseOptions_VideoRenderSelectionParsesAllFlags()
    {
        var options = InvokePrivateStatic<Dictionary<string, string?>>(
            "ParseOptions",
            (object)new[]
            {
                "--project", "demo.atproj",
                "--output", "cut.mp4",
                "--include-audio", "true",
                "--encoder", "libx264",
                "--nvenc-preset", "p5",
                "--cq", "23",
                "--audio-bitrate", "160",
                "--progress", "jsonl"
            });

        Assert.Equal("demo.atproj", options["project"]);
        Assert.Equal("cut.mp4", options["output"]);
        Assert.Equal("true", options["include-audio"]);
        Assert.Equal("libx264", options["encoder"]);
        Assert.Equal("p5", options["nvenc-preset"]);
        Assert.Equal("23", options["cq"]);
        Assert.Equal("160", options["audio-bitrate"]);
        Assert.Equal("jsonl", options["progress"]);
    }

    [Fact]
    public async Task Main_TranscodeQueueMissingSpecReturnsValidationError()
    {
        var exitCode = await InvokeMainAsync(["transcode", "queue", "--spec", "missing.json"]);

        Assert.Equal(1, exitCode);
    }

    [Fact]
    public async Task Main_TranscodeQueueMalformedSpecReturnsFailure()
    {
        using var workspace = new TestWorkspace();
        var specPath = workspace.CreateTextFile("queue/spec.json", "{ bad");

        var exitCode = await InvokeMainAsync(["transcode", "queue", "--spec", specPath]);

        Assert.Equal(3, exitCode);
    }

    [Fact]
    public async Task Main_TranscodeRunMissingInputReturnsFailure()
    {
        using var workspace = new TestWorkspace();
        var outputPath = workspace.PathFor("out/output.mp4");

        var exitCode = await InvokeMainAsync(["transcode", "run", "--input", workspace.PathFor("missing.mp4"), "--output", outputPath]);

        Assert.Equal(3, exitCode);
    }

    [Fact]
    public void ResolveWhisperOptions_CliOverridesConfigAndEnvironment()
    {
        using var workspace = new TestWorkspace();
        var projectPath = workspace.CreateTextFile("project/demo.atproj");
        workspace.CreateTextFile("project/whisper-config.json", """
{
  "executablePath": "config.exe",
  "modelPath": "config.bin",
  "language": "ja",
  "threads": 2,
  "extraArgs": "--config-flag",
  "chunkDurationSeconds": 900,
  "chunkOverlapSeconds": 4.5,
  "resumePartialResults": false
}
""");

        var previousExe = Environment.GetEnvironmentVariable("WHISPER_EXE_PATH");
        var previousModel = Environment.GetEnvironmentVariable("WHISPER_MODEL_PATH");
        var previousLanguage = Environment.GetEnvironmentVariable("WHISPER_LANGUAGE");
        try
        {
            Environment.SetEnvironmentVariable("WHISPER_EXE_PATH", "env.exe");
            Environment.SetEnvironmentVariable("WHISPER_MODEL_PATH", "env.bin");
            Environment.SetEnvironmentVariable("WHISPER_LANGUAGE", "zh");

            var options = InvokePrivateStatic<WhisperOptions>(
                "ResolveWhisperOptions",
                new Dictionary<string, string?>(StringComparer.OrdinalIgnoreCase)
                {
                    ["whisper-exe"] = "cli.exe",
                    ["model"] = "cli.bin",
                    ["language"] = "en",
                    ["threads"] = "8",
                    ["extra-args"] = "--cli-flag",
                    ["chunk-duration"] = "1200",
                    ["chunk-overlap"] = "1.5",
                    ["resume-partials"] = "true"
                },
                projectPath);

            Assert.Equal("cli.exe", options.ExecutablePath);
            Assert.Equal("cli.bin", options.ModelPath);
            Assert.Equal("en", options.Language);
            Assert.Equal(8, options.Threads);
            Assert.Equal("--cli-flag", options.ExtraArgs);
            Assert.Equal(1200, options.ChunkDurationSeconds);
            Assert.Equal(1.5d, options.ChunkOverlapSeconds, 3);
            Assert.True(options.ResumePartialResults);
        }
        finally
        {
            Environment.SetEnvironmentVariable("WHISPER_EXE_PATH", previousExe);
            Environment.SetEnvironmentVariable("WHISPER_MODEL_PATH", previousModel);
            Environment.SetEnvironmentVariable("WHISPER_LANGUAGE", previousLanguage);
        }
    }

    [Fact]
    public void ResolveProjectPathArgument_AcceptsProjectDirectoryWithSingleAtproj()
    {
        using var workspace = new TestWorkspace();
        var projectFilePath = workspace.CreateTextFile("project/demo.atproj");

        var resolvedPath = InvokePrivateStatic<string>("ResolveProjectPathArgument", workspace.PathFor("project"));

        Assert.Equal(Path.GetFullPath(projectFilePath), resolvedPath);
    }

    [Fact]
    public void ResolveVideoEncoderMode_RejectsUnknownValue()
    {
        var exception = Assert.Throws<TargetInvocationException>(() =>
            InvokePrivateStatic<string>("ResolveVideoEncoderMode", "vp9"));

        Assert.IsType<ArgumentException>(exception.InnerException);
    }

    [Fact]
    public void BuildClipConcatSegments_ConvertsIntervalsToSequentialSegments()
    {
        var segments = InvokePrivateStatic<List<ClipConcatSegment>>(
            "BuildClipConcatSegments",
            new List<(double Start, double End)>
            {
                (1.25d, 2.75d),
                (10d, 12.5d)
            });

        Assert.Collection(
            segments,
            first =>
            {
                Assert.Equal(1, first.Sequence);
                Assert.Equal(TimeSpan.FromSeconds(1.25d), first.Start);
                Assert.Equal(TimeSpan.FromSeconds(1.5d), first.Duration);
            },
            second =>
            {
                Assert.Equal(2, second.Sequence);
                Assert.Equal(TimeSpan.FromSeconds(10d), second.Start);
                Assert.Equal(TimeSpan.FromSeconds(2.5d), second.Duration);
            });
    }

    private static async Task<int> InvokeMainAsync(string[] args)
    {
        var method = ProgramType.GetMethod("Main", BindingFlags.Public | BindingFlags.Static)
            ?? throw new InvalidOperationException("Program.Main not found.");

        var task = (Task<int>)method.Invoke(null, [args])!;
        return await task;
    }

    private static T InvokePrivateStatic<T>(string methodName, params object[] args)
    {
        var method = ProgramType.GetMethod(methodName, BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException($"Method not found: {methodName}");

        return (T)method.Invoke(null, args)!;
    }

    private static async Task<T> InvokePrivateStaticAsync<T>(string methodName, params object[] args)
    {
        var method = ProgramType.GetMethod(methodName, BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException($"Method not found: {methodName}");

        var task = (Task)method.Invoke(null, args)!;
        await task;
        var resultProperty = task.GetType().GetProperty("Result")
            ?? throw new InvalidOperationException($"Result property not found: {methodName}");
        return (T)resultProperty.GetValue(task)!;
    }

    private static Type ProgramType =>
        Assembly.Load("AnimeTranscoder.Cli").GetType("AnimeTranscoder.Cli.Program", throwOnError: true)!;
}
