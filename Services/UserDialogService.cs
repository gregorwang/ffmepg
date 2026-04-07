using System.Diagnostics;
using Forms = System.Windows.Forms;

namespace AnimeTranscoder.Services;

public sealed class UserDialogService
{
    private const string MediaFileFilter =
        "Media Files (*.mkv;*.mp4;*.mov;*.m4v;*.avi;*.ts;*.m2ts;*.webm;*.flv;*.wmv;*.mp3;*.aac;*.m4a;*.flac;*.wav;*.ogg;*.opus)|*.mkv;*.mp4;*.mov;*.m4v;*.avi;*.ts;*.m2ts;*.webm;*.flv;*.wmv;*.mp3;*.aac;*.m4a;*.flac;*.wav;*.ogg;*.opus|All Files (*.*)|*.*";

    public IReadOnlyList<string> PickFiles()
    {
        var dialog = new Microsoft.Win32.OpenFileDialog
        {
            Filter = "Video Files (*.mkv;*.mp4;*.mov;*.m4v;*.avi;*.ts;*.m2ts;*.webm)|*.mkv;*.mp4;*.mov;*.m4v;*.avi;*.ts;*.m2ts;*.webm|All Files (*.*)|*.*",
            Multiselect = true,
            CheckFileExists = true
        };

        return dialog.ShowDialog() == true ? dialog.FileNames : [];
    }

    public string? PickMediaFile(string? initialDirectory = null)
    {
        var dialog = new Microsoft.Win32.OpenFileDialog
        {
            Filter = MediaFileFilter,
            Multiselect = false,
            CheckFileExists = true,
            InitialDirectory = string.IsNullOrWhiteSpace(initialDirectory) ? string.Empty : initialDirectory
        };

        return dialog.ShowDialog() == true ? dialog.FileName : null;
    }

    public string? PickFolder(string? initialPath = null)
    {
        using var dialog = new Forms.FolderBrowserDialog
        {
            UseDescriptionForTitle = true,
            Description = "Select folder",
            SelectedPath = string.IsNullOrWhiteSpace(initialPath) ? string.Empty : initialPath
        };

        return dialog.ShowDialog() == Forms.DialogResult.OK ? dialog.SelectedPath : null;
    }

    public void OpenFolder(string path)
    {
        if (Directory.Exists(path))
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = path,
                UseShellExecute = true
            });
        }
    }

    public void OpenFile(string path)
    {
        if (File.Exists(path))
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = path,
                UseShellExecute = true
            });
        }
    }

    public string? PickSaveFile(string title, string filter, string defaultFileName, string? initialDirectory = null)
    {
        var dialog = new Microsoft.Win32.SaveFileDialog
        {
            Title = title,
            Filter = filter,
            FileName = defaultFileName,
            InitialDirectory = string.IsNullOrWhiteSpace(initialDirectory) ? string.Empty : initialDirectory,
            AddExtension = true,
            OverwritePrompt = true
        };

        return dialog.ShowDialog() == true ? dialog.FileName : null;
    }
}
