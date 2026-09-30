using Microsoft.UI.Xaml;
using DisWhisper.Companion.Services;

namespace DisWhisper.Companion;

public partial class App : Application
{
    public static Window? MainWindow { get; private set; }
    public static DisWhisperApiService ApiService { get; private set; } = new();

    public App()
    {
        this.InitializeComponent();
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        MainWindow = new MainWindow();
        MainWindow.Activate();

        ApiService.StartWebSocketListener();
    }
}
