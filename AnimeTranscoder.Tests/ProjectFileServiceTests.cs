using AnimeTranscoder.Services;
using Xunit;

namespace AnimeTranscoder.Tests;

public sealed class ProjectFileServiceTests
{
    [Fact]
    public void Create_UsesProjectRelativeArtifactsDirectory()
    {
        var tempDirectory = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempDirectory);

        var inputPath = Path.Combine(tempDirectory, "input.mp4");
        File.WriteAllText(inputPath, "stub");

        var projectPath = Path.Combine(tempDirectory, "demo.atproj");
        var service = new ProjectFileService();

        var project = service.Create(inputPath, projectPath);

        Assert.Equal(Path.GetFullPath(inputPath), project.InputPath);
        Assert.Equal(Path.Combine(tempDirectory, "demo.artifacts"), project.WorkingDirectory);
        Assert.Equal("initialized", project.Status);
    }
}
