using Microsoft.UI.Xaml;
using Microsoft.Windows.AppLifecycle;
using System;
using System.Text.RegularExpressions;
using ILaunchActivatedEventArgs = Windows.ApplicationModel.Activation.ILaunchActivatedEventArgs;
using DisWhisper.Companion.Services;
using DisWhisper.Companion.Models;
using System.Collections.ObjectModel;
using System.Text.Json;

namespace DisWhisper.Companion;

public partial class App : Application
{
    public static Window? MainWindow { get; private set; }
    public static DisWhisperApiService ApiService { get; private set; } = new();
    public static BackendProcessService BackendService { get; private set; } = null!;
    public static UiPreferences Preferences { get; } = UiPreferences.Load();
    public static ObservableCollection<LiveTranscript> LiveTranscripts { get; } = new();
    private AppInstance? _instance;

    public App()
    {
        this.InitializeComponent();
    }

    protected override async void OnLaunched(LaunchActivatedEventArgs args)
    {
        var preview = Environment.GetCommandLineArgs().Contains("--preview", StringComparer.OrdinalIgnoreCase);
        _instance = AppInstance.FindOrRegisterForKey(preview ? "DisWhisper.Companion.Preview" : "DisWhisper.Companion");
        if (!_instance.IsCurrent)
        {
            await _instance.RedirectActivationToAsync(AppInstance.GetCurrent().GetActivatedEventArgs());
            ApiService.Dispose();
            Exit();
            return;
        }

        if (Environment.GetCommandLineArgs().Contains("--quit", StringComparer.OrdinalIgnoreCase))
        {
            _instance.UnregisterKey();
            ApiService.Dispose();
            Exit();
            return;
        }

        ApiService.Dispose();
        ApiService = new DisWhisperApiService(preview ? "http://127.0.0.1:8767" : "http://127.0.0.1:8765");
        BackendService = new BackendProcessService(ApiService, preview);
        var window = new MainWindow();
        MainWindow = window;
        window.ShowWindow();
        if (Environment.GetCommandLineArgs().Contains("--tray", StringComparer.OrdinalIgnoreCase)) window.HideToTray();
        _instance.Activated += OnInstanceActivated;
        MainWindow.Closed += (s, e) =>
        {
            _instance.Activated -= OnInstanceActivated;
            _instance.UnregisterKey();
            ApiService.Dispose();
        };

        ApiService.OnEventReceived += CacheTranscript;
        ApiService.StartWebSocketListener();
        if (!await BackendService.EnsureRunningAsync())
            TrayIconService.WriteDiagnostic(BackendService.LastError);
    }

    private void CacheTranscript(string name, JsonElement data)
    {
        if (name != "transcript_snippet" || !data.TryGetProperty("text", out var text) || !data.TryGetProperty("speaker", out var speaker)) return;
        var line = new LiveTranscript
        {
            Speaker = speaker.GetString() ?? "Speaker", Text = text.GetString() ?? "",
            Time = data.TryGetProperty("timestamp", out var timestamp) ? DateTimeOffset.FromUnixTimeSeconds((long)timestamp.GetDouble()).ToLocalTime().ToString("HH:mm:ss") : ""
        };
        MainWindow?.DispatcherQueue.TryEnqueue(() =>
        {
            LiveTranscripts.Insert(0, line);
            while (LiveTranscripts.Count > 100) LiveTranscripts.RemoveAt(LiveTranscripts.Count - 1);
        });
    }

    private void OnInstanceActivated(object? sender, AppActivationArguments args)
    {
        var window = MainWindow as MainWindow;
        var commandLine = (args.Data as ILaunchActivatedEventArgs)?.Arguments ?? "";
        window?.DispatcherQueue.TryEnqueue(() =>
        {
            if (Regex.IsMatch(commandLine, @"(?:^|\s)--quit(?:\s|$)", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)) window.Quit();
            else if (Regex.IsMatch(commandLine, @"(?:^|\s)--tray(?:\s|$)", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)) window.HideToTray();
            else window.ShowWindow();
        });
    }
}
