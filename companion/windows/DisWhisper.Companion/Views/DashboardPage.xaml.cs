using System.Collections.ObjectModel;
using System.Text.Json;
using DisWhisper.Companion.Models;
using DisWhisper.Companion.Services;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace DisWhisper.Companion.Views;

public partial class DashboardPage : Page
{
    private bool _loaded;
    private bool _busy;
    private DisWhisperStatus _status = new();

    public DashboardPage()
    {
        InitializeComponent();
        LiveFeed.ItemsSource = App.LiveTranscripts;
        Motion.EnablePressFeedback(ConnectButton);
        Loaded += async (_, _) =>
        {
            _loaded = true;
            App.ApiService.StatusChanged += OnStatus;
            App.LiveTranscripts.CollectionChanged += OnFeedChanged;
            UpdateFeedVisibility();
            Render(await App.ApiService.GetStatusAsync() ?? new());
        };
        Unloaded += (_, _) => { _loaded = false; App.ApiService.StatusChanged -= OnStatus; App.LiveTranscripts.CollectionChanged -= OnFeedChanged; };
    }

    private void OnStatus(DisWhisperStatus status) => DispatcherQueue.TryEnqueue(() => { if (_loaded) Render(status); });

    private void Render(DisWhisperStatus status)
    {
        if (!_loaded) return;
        _status = status;
        BotStatusText.Text = status.Status == "online" ? status.BotUser : status.Status switch { "starting" => "Loading model…", "connecting" => "Connecting…", "idle" => "Ready to connect", "error" => "Needs attention", _ => "Starting service…" };
        VoiceChannelText.Text = status.VoiceConnected ? $"Listening in {status.VoiceChannel}" : "Join a voice channel, then use /join";
        EngineNameText.Text = status.EngineName.Replace(" (faster-whisper)", "");
        EngineDetailsText.Text = $"{status.ModelName} · {(status.Language == "auto" ? "Automatic language" : status.Language.ToUpperInvariant())}";
        DeviceText.Text = !status.EngineLoaded ? "Ready when you are" : status.Device == "cuda" ? "NVIDIA GPU" : status.Device == "cloud" ? "Cloud provider" : "Local CPU";
        PerformanceText.Text = status.VoiceConnected ? $"{status.ActiveSpeakerBuffers} speaker buffers · {status.QueueDepth} chunks waiting" : status.EngineLoaded ? $"{status.ComputeType} · Model loaded" : "Model loads when the bot connects";
        HeroTitle.Text = status.VoiceConnected ? "You're free to focus." : status.Status == "online" ? "Ready for your next conversation." : "A home for every conversation.";
        HeroDescription.Text = status.VoiceConnected ? "The meeting is being transcribed. Finish it here or use /leave in Discord to save and share the transcript." : status.Status == "online" ? "Join your Discord voice channel and use /join. DisWhisper takes care of the transcript." : "Connect your own Discord bot, choose a speech model, and let the conversation flow.";
        ConnectButton.Content = status.VoiceConnected ? "Finish meeting" : status.Status == "offline" ? "Retry local service" : !status.TokenConfigured ? "Set up Discord" : status.Status == "online" ? status.Managed ? "Disconnect bot" : "Bot is connected" : "Connect bot";
        ConnectButton.IsEnabled = !_busy && status.Status is not ("starting" or "connecting") && !(status.Status == "online" && !status.Managed && !status.VoiceConnected);
        PrivacyText.Text = status.EngineName.Contains("Cloud", StringComparison.OrdinalIgnoreCase) ? "This speech provider sends audio to its cloud service. Select Whisper, Vosk, or SenseVoice for speech processing on this PC." : "Speech stays on your PC with local models. Discord carries the call and the transcripts you choose to share.";
        if (status.Status == "error" && !string.IsNullOrEmpty(status.Error)) ShowNotice("Couldn't connect", status.Error, InfoBarSeverity.Error);
        if (status.Status == "offline" && !string.IsNullOrEmpty(App.BackendService.LastError)) ShowNotice("Local service", App.BackendService.LastError, InfoBarSeverity.Warning);
    }

    private void OnFeedChanged(object? sender, System.Collections.Specialized.NotifyCollectionChangedEventArgs e) => UpdateFeedVisibility();
    private void UpdateFeedVisibility()
    { EmptyFeed.Visibility = App.LiveTranscripts.Count == 0 ? Visibility.Visible : Visibility.Collapsed; LiveFeed.Visibility = App.LiveTranscripts.Count == 0 ? Visibility.Collapsed : Visibility.Visible; }

    private async void Connect_Click(object sender, RoutedEventArgs e)
    {
        if (_busy) return;
        if (!_status.TokenConfigured && _status.Status != "offline") { (App.MainWindow as MainWindow)?.NavigateTo("discord"); return; }
        _busy = true; ConnectButton.IsEnabled = false; BusyRing.IsActive = true; BusyRing.Visibility = Visibility.Visible; Notice.IsOpen = false;
        try
        {
            bool ok;
            if (_status.Status == "offline") ok = await App.BackendService.EnsureRunningAsync();
            else if (_status.VoiceConnected) ok = await App.ApiService.FinishMeetingAsync();
            else if (_status.Status == "online") ok = await App.ApiService.StopBotAsync();
            else ok = await App.ApiService.StartBotAsync();
            if (!ok) ShowNotice("One more step", _status.Status == "offline" ? App.BackendService.LastError : App.ApiService.LastError, InfoBarSeverity.Warning);
        }
        finally { _busy = false; BusyRing.IsActive = false; BusyRing.Visibility = Visibility.Collapsed; Render(await App.ApiService.GetStatusAsync() ?? new()); }
    }

    private void Models_Click(object sender, RoutedEventArgs e) => (App.MainWindow as MainWindow)?.NavigateTo("models");
    private void Library_Click(object sender, RoutedEventArgs e) => (App.MainWindow as MainWindow)?.NavigateTo("transcripts");
    private void ShowNotice(string title, string message, InfoBarSeverity severity) { Notice.Title = title; Notice.Message = message; Notice.Severity = severity; Notice.IsOpen = true; }
}
