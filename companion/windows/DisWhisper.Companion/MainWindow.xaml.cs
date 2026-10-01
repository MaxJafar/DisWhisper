using System.Diagnostics;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Animation;
using Microsoft.UI.Windowing;
using DisWhisper.Companion.Models;
using DisWhisper.Companion.Services;
using DisWhisper.Companion.Views;

namespace DisWhisper.Companion;

public partial class MainWindow : Window
{
    private TrayIconService? _trayIcon;
    private bool _quitting;
    private bool _navigating;

    public MainWindow()
    {
        InitializeComponent();
        App.Preferences.Apply(Shell);
        if (Microsoft.UI.Composition.SystemBackdrops.MicaController.IsSupported()) SystemBackdrop = new MicaBackdrop();
        ExtendsContentIntoTitleBar = true;
        SetTitleBar(TitleBar);
        AppWindow.Resize(new Windows.Graphics.SizeInt32(1220, 820));
        AppWindow.TitleBar.ButtonBackgroundColor = Microsoft.UI.Colors.Transparent;
        AppWindow.TitleBar.ButtonInactiveBackgroundColor = Microsoft.UI.Colors.Transparent;
        Shell.ActualThemeChanged += (_, _) => ApplyTitleBarTheme();
        ApplyTitleBarTheme();
        NavigateTo("home");
        var iconPath = Path.Combine(AppContext.BaseDirectory, "Assets", "DisWhisper.ico");
        try
        {
            AppWindow.SetIcon(iconPath);
            _trayIcon = new TrayIconService(WinRT.Interop.WindowNative.GetWindowHandle(this), DispatcherQueue, iconPath, ShowWindow, HideToTray, Quit);
        }
        catch (Exception error) { TrayIconService.WriteDiagnostic($"Tray setup failed: {error.Message}"); }
        AppWindow.Closing += OnClosing;
        App.ApiService.StatusChanged += OnStatusChanged;
        Closed += (_, _) => { _trayIcon?.Dispose(); App.ApiService.StatusChanged -= OnStatusChanged; };
    }

    private void ApplyTitleBarTheme()
    {
        AppWindow.TitleBar.ButtonForegroundColor = Shell.ActualTheme == ElementTheme.Dark ? Microsoft.UI.Colors.White : Microsoft.UI.Colors.Black;
        AppWindow.TitleBar.ButtonInactiveForegroundColor = Microsoft.UI.Colors.Gray;
    }

    public void ApplyAppearance() { App.Preferences.Apply(Shell); ApplyTitleBarTheme(); }

    public void ShowWindow()
    {
        AppWindow.Show();
        if (AppWindow.Presenter is OverlappedPresenter presenter) presenter.Restore();
        Activate();
        TrayIconService.WriteDiagnostic("Companion window shown.");
    }

    internal void HideToTray()
    {
        if (_trayIcon?.IsVisible == true) { AppWindow.Hide(); TrayIconService.WriteDiagnostic("Companion window hidden to tray."); }
    }

    private void OnClosing(AppWindow sender, AppWindowClosingEventArgs args)
    {
        if (!_quitting)
        {
            args.Cancel = true;
            if (_trayIcon?.IsVisible == true) HideToTray();
            else Quit();
        }
    }

    internal async void Quit()
    {
        if (_quitting) return;
        _quitting = true;
        Shell.IsHitTestVisible = false;
        try { await App.BackendService.DisposeAsync(); }
        catch (Exception error) { TrayIconService.WriteDiagnostic($"Shutdown: {error.Message}"); }
        Close();
    }

    private void OnStatusChanged(DisWhisperStatus status) => DispatcherQueue.TryEnqueue(() =>
    {
        SidebarStatus.Text = status.VoiceConnected ? "Transcribing a meeting" : status.Status switch
        { "online" => "Connected to Discord", "starting" => "Loading speech model", "connecting" => "Connecting to Discord", "idle" => "Local service ready", "error" => "Needs your attention", _ => "Starting local service" };
        StatusDot.Fill = (SolidColorBrush)Application.Current.Resources[status.Status is "online" or "idle" ? "DisWhisperGreenBrush" : "DisWhisperOrangeBrush"];
    });

    public void NavigateTo(string tag, object? parameter = null)
    {
        _navigating = true;
        foreach (var item in AllNavigationItems()) if (item.Tag?.ToString() == tag) { NavView.SelectedItem = item; break; }
        _navigating = false;
        var page = tag switch
        { "models" => typeof(ModelsPage), "transcripts" => typeof(TranscriptsPage), "discord" => typeof(DiscordSetupPage), "settings" => typeof(SettingsPage), "summaries" or "extras" => typeof(SummariesPage), "cloud" => typeof(CloudProvidersPage), _ => typeof(DashboardPage) };
        if (ContentFrame.CurrentSourcePageType != page || parameter != null)
            ContentFrame.Navigate(page, parameter, Motion.Enabled ? new EntranceNavigationTransitionInfo() : new SuppressNavigationTransitionInfo());
    }

    private IEnumerable<NavigationViewItem> AllNavigationItems()
    {
        foreach (var item in NavView.MenuItems.Concat(NavView.FooterMenuItems).OfType<NavigationViewItem>())
        { yield return item; foreach (var child in item.MenuItems.OfType<NavigationViewItem>()) yield return child; }
    }

    private void NavView_SelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    { if (!_navigating && args.SelectedItem is NavigationViewItem item) NavigateTo(item.Tag?.ToString() ?? "home"); }
    private void Source_Click(object sender, RoutedEventArgs e) => Process.Start(new ProcessStartInfo("https://github.com/MaxJafar/DisWhisper") { UseShellExecute = true });
    private void HomeShortcut(KeyboardAccelerator sender, KeyboardAcceleratorInvokedEventArgs args) { NavigateTo("home"); args.Handled = true; }
    private void ModelsShortcut(KeyboardAccelerator sender, KeyboardAcceleratorInvokedEventArgs args) { NavigateTo("models"); args.Handled = true; }
    private void TranscriptsShortcut(KeyboardAccelerator sender, KeyboardAcceleratorInvokedEventArgs args) { NavigateTo("transcripts"); args.Handled = true; }
    private void SettingsShortcut(KeyboardAccelerator sender, KeyboardAcceleratorInvokedEventArgs args) { NavigateTo("settings"); args.Handled = true; }
}
