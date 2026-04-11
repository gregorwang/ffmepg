using AnimeTranscoder.Composition;
using AnimeTranscoder.Services;
using AnimeTranscoder.ViewModels;
using MessageBox = System.Windows.MessageBox;

namespace AnimeTranscoder.Views;

public partial class MainWindow : System.Windows.Window
{
    public MainWindow()
    {
        InitializeComponent();

        DataContext = new AppCompositionRoot().CreateMainViewModel();

        if (DataContext is MainViewModel viewModel)
        {
            viewModel.QueueCompleted += OnQueueCompleted;
        }

        Closed += OnClosed;
    }

    private void Window_DragEnter(object sender, System.Windows.DragEventArgs e)
    {
        if (DataContext is MainViewModel viewModel)
        {
            viewModel.IsDropTargetActive = e.Data.GetDataPresent(System.Windows.DataFormats.FileDrop);
        }
    }

    private void Window_DragLeave(object sender, System.Windows.DragEventArgs e)
    {
        if (DataContext is MainViewModel viewModel)
        {
            viewModel.IsDropTargetActive = false;
        }
    }

    private void Window_DragOver(object sender, System.Windows.DragEventArgs e)
    {
        var acceptsDrop = e.Data.GetDataPresent(System.Windows.DataFormats.FileDrop);
        e.Effects = acceptsDrop ? System.Windows.DragDropEffects.Copy : System.Windows.DragDropEffects.None;
        e.Handled = true;

        if (DataContext is MainViewModel viewModel)
        {
            viewModel.IsDropTargetActive = acceptsDrop;
        }
    }

    private void Window_Drop(object sender, System.Windows.DragEventArgs e)
    {
        if (DataContext is not MainViewModel viewModel)
        {
            return;
        }

        if (e.Data.GetData(System.Windows.DataFormats.FileDrop) is string[] paths)
        {
            viewModel.IsDropTargetActive = false;
            viewModel.AddPaths(paths);
        }
    }

    private void OnQueueCompleted(string title, string summary)
    {
        _ = Dispatcher.InvokeAsync(() =>
        {
            MessageBox.Show(this, summary, title, System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Information);
        });
    }

    private void OnClosed(object? sender, EventArgs e)
    {
        if (DataContext is IDisposable disposable)
        {
            disposable.Dispose();
        }
    }
}
