using System.Text;

namespace AnimeTranscoder.Tests;

internal sealed class TestWorkspace : IDisposable
{
    public TestWorkspace()
    {
        RootPath = Path.Combine(Path.GetTempPath(), "AnimeTranscoder.Tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(RootPath);
    }

    public string RootPath { get; }

    public string PathFor(string relativePath)
    {
        return Path.Combine(RootPath, relativePath);
    }

    public string CreateTextFile(string relativePath, string content = "test")
    {
        var path = PathFor(relativePath);
        var directory = Path.GetDirectoryName(path);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        File.WriteAllText(path, content, Encoding.UTF8);
        return path;
    }

    public string CreateBinaryFile(string relativePath, byte[] content)
    {
        var path = PathFor(relativePath);
        var directory = Path.GetDirectoryName(path);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        File.WriteAllBytes(path, content);
        return path;
    }

    public string CreateWaveFile(string relativePath, int sampleRate = 16000, short channels = 1, short bitsPerSample = 16, short[]? samples = null)
    {
        samples ??= [0, 1000, -1000, 500, -500, 0];

        var data = new byte[samples.Length * sizeof(short)];
        Buffer.BlockCopy(samples, 0, data, 0, data.Length);

        using var buffer = new MemoryStream();
        using (var writer = new BinaryWriter(buffer, Encoding.ASCII, leaveOpen: true))
        {
            writer.Write(Encoding.ASCII.GetBytes("RIFF"));
            writer.Write(36 + data.Length);
            writer.Write(Encoding.ASCII.GetBytes("WAVE"));
            writer.Write(Encoding.ASCII.GetBytes("fmt "));
            writer.Write(16);
            writer.Write((short)1);
            writer.Write(channels);
            writer.Write(sampleRate);
            writer.Write(sampleRate * channels * bitsPerSample / 8);
            writer.Write((short)(channels * bitsPerSample / 8));
            writer.Write(bitsPerSample);
            writer.Write(Encoding.ASCII.GetBytes("data"));
            writer.Write(data.Length);
            writer.Write(data);
        }

        return CreateBinaryFile(relativePath, buffer.ToArray());
    }

    public void Dispose()
    {
        if (Directory.Exists(RootPath))
        {
            Directory.Delete(RootPath, recursive: true);
        }
    }
}
