using AnimeTranscoder.Infrastructure;
using MessageBox = System.Windows.MessageBox;

namespace AnimeTranscoder;

public partial class App : System.Windows.Application
{
    protected override void OnStartup(System.Windows.StartupEventArgs e)
    {
        AppFileLogger.Write("App", "应用启动。");

        DispatcherUnhandledException += OnDispatcherUnhandledException;
        AppDomain.CurrentDomain.UnhandledException += OnCurrentDomainUnhandledException;
        TaskScheduler.UnobservedTaskException += OnUnobservedTaskException;

        base.OnStartup(e);
    }

    protected override void OnExit(System.Windows.ExitEventArgs e)
    {
        AppFileLogger.Write("App", $"应用退出，代码：{e.ApplicationExitCode}");
        base.OnExit(e);
    }

    private void OnDispatcherUnhandledException(object sender, System.Windows.Threading.DispatcherUnhandledExceptionEventArgs e)
    {
        AppFileLogger.WriteException("DispatcherUnhandledException", e.Exception);
        MessageBox.Show(
            $"程序发生未处理异常，详情已写入日志：{AppFileLogger.CurrentLogPath}",
            "AnimeTranscoder",
            System.Windows.MessageBoxButton.OK,
            System.Windows.MessageBoxImage.Error);

        e.Handled = true;
        Shutdown(-1);
    }

    private void OnCurrentDomainUnhandledException(object? sender, UnhandledExceptionEventArgs e)
    {
        if (e.ExceptionObject is Exception exception)
        {
            AppFileLogger.WriteException("AppDomainUnhandledException", exception);
            return;
        }

        AppFileLogger.Write("AppDomainUnhandledException", $"发生未知异常对象：{e.ExceptionObject}");
    }

    private void OnUnobservedTaskException(object? sender, UnobservedTaskExceptionEventArgs e)
    {
        AppFileLogger.WriteException("UnobservedTaskException", e.Exception);
        e.SetObserved();
    }
}
