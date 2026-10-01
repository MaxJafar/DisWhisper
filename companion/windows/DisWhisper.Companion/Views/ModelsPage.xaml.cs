using System;
using System.Diagnostics;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using DisWhisper.Companion.Models;
using DisWhisper.Companion.Services;

namespace DisWhisper.Companion.Views;

public partial class ModelsPage : Page
{
    private List<ModelInfo> _models = new();
    private readonly DispatcherTimer _progressTimer = new() { Interval = TimeSpan.FromSeconds(3) };
    private bool _refreshing;
    private bool _polling;
    private bool _loaded;

    public ModelsPage()
    {
        InitializeComponent();
        Loaded += async (s, e) =>
        {
            _loaded = true;
            App.ApiService.OnEventReceived += OnBackendEvent;
            _progressTimer.Start();
            await RefreshModelsAsync();
        };
        Unloaded += (s, e) =>
        {
            _loaded = false;
            _progressTimer.Stop();
            App.ApiService.OnEventReceived -= OnBackendEvent;
        };
        _progressTimer.Tick += async (s, e) => await PollProgressAsync();
    }

    private async Task RefreshModelsAsync()
    {
        if (_refreshing) return;
        _refreshing = true;
        try
        {
            var models = await App.ApiService.GetModelsAsync();
            if (!_loaded) return;
            _models = models;
            FilterModels();
            if (models.Count == 0) ShowNotice("Backend unavailable", App.ApiService.LastError, InfoBarSeverity.Warning);
            await PollProgressAsync();
        }
        finally { _refreshing = false; }
    }

    private async Task PollProgressAsync()
    {
        if (_polling || !_loaded) return;
        _polling = true;
        try
        {
            var progress = await App.ApiService.GetDownloadProgressAsync();
            if (!_loaded) return;
            foreach (var (id, state) in progress) ApplyProgress(id, state);
        }
        finally { _polling = false; }
    }

    private void ApplyProgress(string id, DownloadProgress state)
    {
        _models.FirstOrDefault(m => m.Id == id)?.SetProgress(state.Status, state.Percent, state.Detail, state.Error);
    }

    private void OnBackendEvent(string eventName, JsonElement data)
    {
        DispatcherQueue.TryEnqueue(async () =>
        {
            if (!_loaded) return;
            if (eventName == "download_progress" && data.TryGetProperty("model_id", out var id))
            {
                var progress = JsonSerializer.Deserialize<DownloadProgress>(data.GetRawText());
                if (progress != null)
                {
                    ApplyProgress(id.GetString() ?? "", progress);
                    if (progress.Status == "completed") await RefreshModelsAsync();
                }
            }
            else if (eventName is "engine_switched" or "config_updated" or "connected")
                await RefreshModelsAsync();
        });
    }

    private async void ActivateModel_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button button || button.Tag is not string id) return;
        button.IsEnabled = false;
        var ok = await App.ApiService.ActivateModelAsync(id);
        if (_loaded)
        {
            ShowNotice(ok ? "Model selected" : "Couldn't select model", ok ? "This model will be used when the bot connects. An already connected bot switches now." : App.ApiService.LastError,
                ok ? InfoBarSeverity.Success : InfoBarSeverity.Error);
            await RefreshModelsAsync();
        }
    }

    private async void DownloadModel_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button button || button.Tag is not string id) return;
        ApplyProgress(id, new DownloadProgress { Status = "downloading", Detail = "Starting download" });
        if (!await App.ApiService.DownloadModelAsync(id))
            ApplyProgress(id, new DownloadProgress { Status = "failed", Error = App.ApiService.LastError });
        else await PollProgressAsync();
    }

    private async void Refresh_Click(object sender, RoutedEventArgs e) => await RefreshModelsAsync();

    private void FilterModels()
    {
        var query = SearchBox.Text.Trim();
        var models = _models.Where(model => (model.Name + " " + string.Join(" ", model.Languages) + " " + model.Description).Contains(query, StringComparison.OrdinalIgnoreCase)).ToList();
        SpeechModels.ItemsSource = models.Where(m => m.Category == "local_stt").OrderBy(m => m.Id == "whisper-base" ? 0 : 1).ToList();
        SummaryModels.ItemsSource = models.Where(m => m.Category == "local_llm").ToList();
        CloudModels.ItemsSource = models.Where(m => m.Category == "cloud_stt").ToList();
    }

    private void Search_Changed(AutoSuggestBox sender, AutoSuggestBoxTextChangedEventArgs args) { if (_loaded && args.Reason == AutoSuggestionBoxTextChangeReason.UserInput) FilterModels(); }
    private void Action_Loaded(object sender, RoutedEventArgs e) { if (sender is FrameworkElement element) Motion.EnablePressFeedback(element); }
    private async void Cancel_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button button || button.Tag is not string id) return;
        button.IsEnabled = false;
        try { if (!await App.ApiService.CancelDownloadAsync(id)) ShowNotice("Couldn't cancel", App.ApiService.LastError, InfoBarSeverity.Warning); await PollProgressAsync(); }
        finally { button.IsEnabled = true; }
    }
    private void Source_Click(object sender, RoutedEventArgs e)
    { if (sender is HyperlinkButton button && button.Tag is string address && Uri.TryCreate(address, UriKind.Absolute, out var uri) && uri.Scheme == "https") Process.Start(new ProcessStartInfo(uri.AbsoluteUri) { UseShellExecute = true }); }
    private void Ollama_Click(object sender, RoutedEventArgs e) => Process.Start(new ProcessStartInfo("https://ollama.com/download/windows") { UseShellExecute = true });
    private void Cloud_Click(object sender, RoutedEventArgs e) => (App.MainWindow as MainWindow)?.NavigateTo("cloud");

    private void ShowNotice(string title, string message, InfoBarSeverity severity)
    {
        ModelNotice.Title = title;
        ModelNotice.Message = message;
        ModelNotice.Severity = severity;
        ModelNotice.IsOpen = true;
    }
}
