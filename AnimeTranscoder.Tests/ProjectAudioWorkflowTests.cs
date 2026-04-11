using AnimeTranscoder.Models;
using AnimeTranscoder.Services;
using AnimeTranscoder.Workflows;
using Xunit;

namespace AnimeTranscoder.Tests;

public sealed class ProjectAudioWorkflowTests
{
    [Fact]
    public async Task InitializeAsync_CreatesAndPersistsProjectFile()
    {
        using var workspace = new TestWorkspace();
        var projectService = new ProjectFileService();
        var inputPath = workspace.CreateTextFile("input/source.mp4");
        var projectPath = workspace.PathFor("project/demo.atproj");
        var workflow = new ProjectAudioWorkflow(
            new ProjectAudioWorkflowDependencies
            {
                LoadProjectAsync = projectService.LoadAsync,
                SaveProjectAsync = projectService.SaveAsync,
                LoadTranscriptAsync = (_, _) => Task.FromResult(new TranscriptDocument()),
                SaveTranscriptAsync = (_, _, _) => Task.CompletedTask,
                LoadSelectionAsync = (_, _) => Task.FromResult(new SelectionDocument()),
                ExtractWorkAudioAsync = (_, output, _, _, _, _) => Task.FromResult(new AudioExtractionResult { Success = true, OutputPath = output }),
                RenderSelectionAsync = (_, output, _, _, _, _, _) => Task.FromResult(new AudioExtractionResult { Success = true, OutputPath = output }),
                ProbeMediaAsync = (_, _) => Task.FromResult<MediaProbeResult?>(new MediaProbeResult())
            },
            projectService);

        var project = await workflow.InitializeAsync(inputPath, projectPath, CancellationToken.None);

        Assert.Equal(Path.GetFullPath(inputPath), project.InputPath);
        Assert.Equal(Path.Combine(Path.GetDirectoryName(projectPath)!, "demo.artifacts"), project.WorkingDirectory);
        Assert.True(File.Exists(projectPath));
    }

    [Fact]
    public async Task ExportWorkAudioAsync_HappyPathUpdatesProject()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        state.ExtractWorkAudioAsync = (input, output, track, sampleRate, _, _) =>
        {
            File.WriteAllText(output, "wav");
            return Task.FromResult(new AudioExtractionResult { Success = true, OutputPath = output });
        };

        var workflow = CreateWorkflow(state);
        var result = await workflow.ExportWorkAudioAsync("demo.atproj", 1, 16000, progress: null, CancellationToken.None);

        Assert.True(result.Success);
        Assert.Equal("work_audio_exported", state.Project.Status);
        Assert.Equal(Path.Combine(state.Project.WorkingDirectory, "work-audio.wav"), state.Project.WorkingAudioPath);
        Assert.Equal(1, state.Project.SelectedAudioTrackIndex);
    }

    [Fact]
    public async Task ExportWorkAudioAsync_MissingInputReturnsFailure()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        File.Delete(state.Project.InputPath);

        var workflow = CreateWorkflow(state);
        var result = await workflow.ExportWorkAudioAsync("demo.atproj", null, 16000, progress: null, CancellationToken.None);

        Assert.False(result.Success);
        Assert.Equal("输入文件不存在", result.ErrorMessage);
    }

    [Fact]
    public async Task ExportWorkAudioAsync_NoAudioTrackReturnsFailure()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        state.ProbeMediaAsync = (_, _) => Task.FromResult<MediaProbeResult?>(new MediaProbeResult
        {
            Path = state.Project.InputPath,
            Duration = TimeSpan.FromSeconds(90),
            AudioTracks = []
        });

        var workflow = CreateWorkflow(state);
        var result = await workflow.ExportWorkAudioAsync("demo.atproj", null, 16000, progress: null, CancellationToken.None);

        Assert.False(result.Success);
        Assert.Equal("输入媒体没有音轨", result.ErrorMessage);
    }

    [Fact]
    public async Task ExportWorkAudioAsync_InvalidTrackReturnsFailure()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        var workflow = CreateWorkflow(state);

        var result = await workflow.ExportWorkAudioAsync("demo.atproj", 9, 16000, progress: null, CancellationToken.None);

        Assert.False(result.Success);
        Assert.Equal("音轨索引无效：9", result.ErrorMessage);
    }

    [Fact]
    public async Task ExportWorkAudioAsync_PropagatesCancelledResult()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        state.ExtractWorkAudioAsync = (_, output, _, _, _, _) => Task.FromResult(new AudioExtractionResult
        {
            Success = false,
            OutputPath = output,
            ErrorMessage = "已取消"
        });

        var workflow = CreateWorkflow(state);
        var result = await workflow.ExportWorkAudioAsync("demo.atproj", null, 16000, progress: null, CancellationToken.None);

        Assert.False(result.Success);
        Assert.Equal("已取消", result.ErrorMessage);
    }

    [Fact]
    public async Task ExportWorkAudioAsync_ThrowsWhenCancellationTriggeredMidOperation()
    {
        using var workspace = new TestWorkspace();
        using var cancellationTokenSource = new CancellationTokenSource();
        var state = CreateDefaultState(workspace);
        state.ExtractWorkAudioAsync = (_, _, _, _, _, ct) =>
        {
            cancellationTokenSource.Cancel();
            ct.ThrowIfCancellationRequested();
            return Task.FromResult(new AudioExtractionResult());
        };

        var workflow = CreateWorkflow(state);

        await Assert.ThrowsAsync<OperationCanceledException>(() =>
            workflow.ExportWorkAudioAsync("demo.atproj", null, 16000, progress: null, cancellationTokenSource.Token));
    }

    [Fact]
    public async Task ImportTranscriptAsync_UpdatesProjectPath()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        var transcriptPath = workspace.PathFor("protocol/transcript.json");
        await new TranscriptDocumentService().SaveAsync(transcriptPath, state.Transcript);

        var workflow = CreateWorkflow(state);
        var project = await workflow.ImportTranscriptAsync("demo.atproj", transcriptPath, CancellationToken.None);

        Assert.Equal(Path.GetFullPath(transcriptPath), project.TranscriptPath);
        Assert.Equal("transcript_imported", project.Status);
    }

    [Fact]
    public async Task ImportTranscriptAsync_MalformedJsonThrowsClearError()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        var transcriptPath = workspace.CreateTextFile("protocol/transcript.json", "{not-json");
        state.LoadTranscriptAsync = new TranscriptDocumentService().LoadAsync;

        var workflow = CreateWorkflow(state);
        var ex = await Assert.ThrowsAsync<InvalidOperationException>(() =>
            workflow.ImportTranscriptAsync("demo.atproj", transcriptPath, CancellationToken.None));

        Assert.Contains("JSON 格式无效", ex.Message);
    }

    [Fact]
    public async Task ImportTranscriptAsync_WrongSchemaThrowsValidationError()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        var transcriptPath = workspace.PathFor("protocol/transcript.json");
        workspace.CreateTextFile("protocol/transcript.json", """
{
  "segments": [
    { "id": "", "start": 0, "end": 1, "text": "bad", "source": "test" }
  ]
}
""");
        state.LoadTranscriptAsync = new TranscriptDocumentService().LoadAsync;

        var workflow = CreateWorkflow(state);
        var ex = await Assert.ThrowsAsync<InvalidOperationException>(() =>
            workflow.ImportTranscriptAsync("demo.atproj", transcriptPath, CancellationToken.None));

        Assert.Contains("缺少 id", ex.Message);
    }

    [Fact]
    public async Task ImportSelectionAsync_UpdatesProjectPath()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        var selectionPath = workspace.PathFor("protocol/selection.json");
        await new SelectionDocumentService().SaveAsync(selectionPath, state.Selection);

        var workflow = CreateWorkflow(state);
        var project = await workflow.ImportSelectionAsync("demo.atproj", selectionPath, CancellationToken.None);

        Assert.Equal(Path.GetFullPath(selectionPath), project.SelectionPath);
        Assert.Equal("selection_imported", project.Status);
    }

    [Fact]
    public async Task RenderSelectionAsync_HappyPathUpdatesProject()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        state.Project.TranscriptPath = workspace.PathFor("protocol/transcript.json");
        state.Project.SelectionPath = workspace.PathFor("protocol/selection.json");
        state.RenderSelectionAsync = (_, output, _, _, _, _, _) =>
        {
            Directory.CreateDirectory(Path.GetDirectoryName(output)!);
            File.WriteAllText(output, "rendered");
            return Task.FromResult(new AudioExtractionResult { Success = true, OutputPath = output });
        };

        var workflow = CreateWorkflow(state);
        var result = await workflow.RenderSelectionAsync("demo.atproj", workspace.PathFor("out/render/output.wav"), AudioRenderMode.Concat, progress: null, CancellationToken.None);

        Assert.True(result.Success);
        Assert.Equal("selection_rendered", state.Project.Status);
        Assert.True(File.Exists(result.OutputPath));
    }

    [Fact]
    public async Task RenderSelectionAsync_CreatesMissingOutputDirectoryBeforeRendering()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        state.Project.TranscriptPath = workspace.PathFor("protocol/transcript.json");
        state.Project.SelectionPath = workspace.PathFor("protocol/selection.json");
        var outputPath = workspace.PathFor("missing/out/render.wav");
        var directoryExistedWhenDelegateRan = false;
        state.RenderSelectionAsync = (_, output, _, _, _, _, _) =>
        {
            directoryExistedWhenDelegateRan = Directory.Exists(Path.GetDirectoryName(output)!);
            File.WriteAllText(output, "rendered");
            return Task.FromResult(new AudioExtractionResult { Success = true, OutputPath = output });
        };

        var workflow = CreateWorkflow(state);
        var result = await workflow.RenderSelectionAsync("demo.atproj", outputPath, AudioRenderMode.PreserveTimeline, progress: null, CancellationToken.None);

        Assert.True(result.Success);
        Assert.True(directoryExistedWhenDelegateRan);
    }

    [Fact]
    public async Task RenderSelectionAsync_EmptySelectionReturnsFailure()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        state.Project.TranscriptPath = workspace.PathFor("protocol/transcript.json");
        state.Project.SelectionPath = workspace.PathFor("protocol/selection.json");
        state.Selection = new SelectionDocument { TargetSegments = [] };
        state.LoadSelectionAsync = (_, _) => Task.FromResult(state.Selection);
        state.RenderSelectionAsync = (_, output, transcript, selection, _, _, _) =>
        {
            var intervals = AudioSelectionRenderService.ResolveKeepIntervals(transcript, selection);
            return Task.FromResult(new AudioExtractionResult
            {
                Success = intervals.Count > 0,
                OutputPath = output,
                ErrorMessage = intervals.Count == 0 ? "Selection 没有可保留的片段" : null
            });
        };

        var workflow = CreateWorkflow(state);
        var result = await workflow.RenderSelectionAsync("demo.atproj", workspace.PathFor("out/empty.wav"), AudioRenderMode.PreserveTimeline, progress: null, CancellationToken.None);

        Assert.False(result.Success);
        Assert.Equal("Selection 没有可保留的片段", result.ErrorMessage);
    }

    [Fact]
    public async Task RenderSelectionAsync_MissingSegmentReferenceThrows()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        state.Project.TranscriptPath = workspace.PathFor("protocol/transcript.json");
        state.Project.SelectionPath = workspace.PathFor("protocol/selection.json");
        state.Selection = new SelectionDocument
        {
            TargetSegments = [new SelectionTargetSegment { SegmentId = "missing", Action = SelectionAction.Keep, Reason = "bad" }]
        };
        state.LoadSelectionAsync = (_, _) => Task.FromResult(state.Selection);
        state.RenderSelectionAsync = (_, output, transcript, selection, _, _, _) =>
        {
            _ = AudioSelectionRenderService.ResolveKeepIntervals(transcript, selection);
            return Task.FromResult(new AudioExtractionResult { Success = true, OutputPath = output });
        };

        var workflow = CreateWorkflow(state);

        var ex = await Assert.ThrowsAsync<InvalidOperationException>(() =>
            workflow.RenderSelectionAsync("demo.atproj", workspace.PathFor("out/error.wav"), AudioRenderMode.PreserveTimeline, progress: null, CancellationToken.None));

        Assert.Contains("不存在的 segmentId", ex.Message);
    }

    [Fact]
    public async Task RenderSelectionAsync_MissingWorkingAudioReturnsFailure()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        state.Project.TranscriptPath = workspace.PathFor("protocol/transcript.json");
        state.Project.SelectionPath = workspace.PathFor("protocol/selection.json");
        File.Delete(state.Project.WorkingAudioPath);

        var workflow = CreateWorkflow(state);
        var result = await workflow.RenderSelectionAsync("demo.atproj", workspace.PathFor("out/missing.wav"), AudioRenderMode.PreserveTimeline, progress: null, CancellationToken.None);

        Assert.False(result.Success);
        Assert.Equal("工作音频文件不存在", result.ErrorMessage);
    }

    [Fact]
    public async Task RenderSelectionAsync_ZeroByteWorkAudioReturnsFailure()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        state.Project.TranscriptPath = workspace.PathFor("protocol/transcript.json");
        state.Project.SelectionPath = workspace.PathFor("protocol/selection.json");
        File.WriteAllBytes(state.Project.WorkingAudioPath, []);

        var workflow = CreateWorkflow(state);
        var result = await workflow.RenderSelectionAsync("demo.atproj", workspace.PathFor("out/zero.wav"), AudioRenderMode.PreserveTimeline, progress: null, CancellationToken.None);

        Assert.False(result.Success);
        Assert.Equal("工作音频文件为空", result.ErrorMessage);
    }

    [Fact]
    public async Task GenerateTranscriptAsync_SavesTranscriptAndUpdatesProject()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        var projectPath = workspace.PathFor("project/demo.atproj");
        state.TranscribeAsync = (_, _, _, _) => Task.FromResult(new TranscriptDocument
        {
            AudioPath = state.Project.WorkingAudioPath,
            Segments = [new TranscriptSegment { Id = "seg_001", Start = 0, End = 1.2, Text = "hello", Source = "whisper.cpp" }]
        });

        var workflow = CreateWorkflow(state);
        var project = await workflow.GenerateTranscriptAsync(projectPath, new WhisperOptions(), progress: null, CancellationToken.None);

        Assert.Equal(Path.Combine(Path.GetDirectoryName(projectPath)!, "transcript.json"), project.TranscriptPath);
        Assert.Equal("transcript_generated", project.Status);
        Assert.Single(state.SavedTranscripts);
    }

    [Fact]
    public async Task GenerateTranscriptAsync_RejectsMissingWorkAudio()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        File.Delete(state.Project.WorkingAudioPath);
        state.TranscribeAsync = (_, _, _, _) => Task.FromResult(state.Transcript);

        var workflow = CreateWorkflow(state);

        await Assert.ThrowsAsync<FileNotFoundException>(() =>
            workflow.GenerateTranscriptAsync("demo.atproj", new WhisperOptions(), progress: null, CancellationToken.None));
    }

    [Fact]
    public async Task GenerateTranscriptAsync_RejectsZeroByteWorkAudio()
    {
        using var workspace = new TestWorkspace();
        var state = CreateDefaultState(workspace);
        File.WriteAllBytes(state.Project.WorkingAudioPath, []);
        state.TranscribeAsync = (_, _, _, _) => Task.FromResult(state.Transcript);

        var workflow = CreateWorkflow(state);
        var ex = await Assert.ThrowsAsync<InvalidOperationException>(() =>
            workflow.GenerateTranscriptAsync("demo.atproj", new WhisperOptions(), progress: null, CancellationToken.None));

        Assert.Contains("工作音频文件为空", ex.Message);
    }

    private static ProjectAudioWorkflow CreateWorkflow(WorkflowState state, ProjectFileService? projectFileService = null)
    {
        return new ProjectAudioWorkflow(
            new ProjectAudioWorkflowDependencies
            {
                LoadProjectAsync = (_, _) => Task.FromResult(CloneProject(state.Project)),
                SaveProjectAsync = (_, project, _) =>
                {
                    state.Project = CloneProject(project);
                    return Task.CompletedTask;
                },
                LoadTranscriptAsync = state.LoadTranscriptAsync,
                SaveTranscriptAsync = (path, document, _) =>
                {
                    state.SavedTranscripts[path] = document;
                    return Task.CompletedTask;
                },
                LoadSelectionAsync = state.LoadSelectionAsync,
                ExtractWorkAudioAsync = state.ExtractWorkAudioAsync,
                RenderSelectionAsync = state.RenderSelectionAsync,
                ProbeMediaAsync = state.ProbeMediaAsync,
                TranscribeAsync = state.TranscribeAsync
            },
            projectFileService);
    }

    private static WorkflowState CreateDefaultState(TestWorkspace workspace)
    {
        var inputPath = workspace.CreateTextFile("media/input.mp4");
        var workAudioPath = workspace.CreateTextFile("project/demo.artifacts/work-audio.wav", "wav");

        return new WorkflowState
        {
            Project = new AnimeProjectFile
            {
                InputPath = inputPath,
                WorkingDirectory = workspace.PathFor("project/demo.artifacts"),
                WorkingAudioPath = workAudioPath,
                SelectedAudioTrackIndex = 0,
                Status = "initialized"
            },
            Transcript = new TranscriptDocument
            {
                AudioPath = workAudioPath,
                Segments = [new TranscriptSegment { Id = "seg_001", Start = 0, End = 1, Text = "a", Source = "test" }]
            },
            Selection = new SelectionDocument
            {
                TargetSegments = [new SelectionTargetSegment { SegmentId = "seg_001", Action = SelectionAction.Keep, Reason = "keep" }]
            },
            LoadTranscriptAsync = (_, _) => Task.FromResult(new TranscriptDocument
            {
                AudioPath = workAudioPath,
                Segments = [new TranscriptSegment { Id = "seg_001", Start = 0, End = 1, Text = "a", Source = "test" }]
            }),
            LoadSelectionAsync = (_, _) => Task.FromResult(new SelectionDocument
            {
                TargetSegments = [new SelectionTargetSegment { SegmentId = "seg_001", Action = SelectionAction.Keep, Reason = "keep" }]
            })
        };
    }

    private static AnimeProjectFile CloneProject(AnimeProjectFile project)
    {
        return new AnimeProjectFile
        {
            InputPath = project.InputPath,
            WorkingDirectory = project.WorkingDirectory,
            SelectedAudioTrackIndex = project.SelectedAudioTrackIndex,
            WorkingAudioPath = project.WorkingAudioPath,
            TranscriptPath = project.TranscriptPath,
            SelectionPath = project.SelectionPath,
            Status = project.Status,
            UpdatedAtUtc = project.UpdatedAtUtc
        };
    }

    private sealed class WorkflowState
    {
        public AnimeProjectFile Project { get; set; } = new();
        public TranscriptDocument Transcript { get; set; } = new();
        public SelectionDocument Selection { get; set; } = new();
        public Dictionary<string, TranscriptDocument> SavedTranscripts { get; } = new(StringComparer.OrdinalIgnoreCase);
        public Func<string, CancellationToken, Task<TranscriptDocument>> LoadTranscriptAsync { get; set; } =
            (_, _) => Task.FromResult(new TranscriptDocument());
        public Func<string, CancellationToken, Task<SelectionDocument>> LoadSelectionAsync { get; set; } =
            (_, _) => Task.FromResult(new SelectionDocument());
        public Func<string, string, int?, int, Action<double, string>?, CancellationToken, Task<AudioExtractionResult>> ExtractWorkAudioAsync { get; set; } =
            (_, output, _, _, _, _) => Task.FromResult(new AudioExtractionResult { Success = true, OutputPath = output });
        public Func<string, string, TranscriptDocument, SelectionDocument, AudioRenderMode, Action<double, string>?, CancellationToken, Task<AudioExtractionResult>> RenderSelectionAsync { get; set; } =
            (_, output, _, _, _, _, _) => Task.FromResult(new AudioExtractionResult { Success = true, OutputPath = output });
        public Func<string, CancellationToken, Task<MediaProbeResult?>> ProbeMediaAsync { get; set; } =
            (_, _) => Task.FromResult<MediaProbeResult?>(new MediaProbeResult
            {
                Duration = TimeSpan.FromSeconds(90),
                AudioTracks = [new AudioTrackInfo { Index = 0 }, new AudioTrackInfo { Index = 1 }]
            });
        public Func<string, WhisperOptions, IProgress<double>?, CancellationToken, Task<TranscriptDocument>>? TranscribeAsync { get; set; }
    }
}
