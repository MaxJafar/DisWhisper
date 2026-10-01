using System.Net.Http;
using DisWhisper.Companion.Services;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace DisWhisper.Companion.Views;

public partial class CloudProvidersPage : Page
{
    private bool _busy;
    public CloudProvidersPage()
    {
        InitializeComponent();
        Motion.EnablePressFeedback(SaveButton);
        Loaded += async (_, _) => await LoadKeysAsync();
    }
    private async Task LoadKeysAsync()
    {
        var cfg = await App.ApiService.GetConfigAsync();
        if (cfg == null) { Show("Local service unavailable", App.ApiService.LastError, InfoBarSeverity.Warning); return; }
        foreach (var (key, box) in new[] { ("GROQ_API_KEY", GroqApiKeyBox), ("OPENAI_API_KEY", OpenAiApiKeyBox) })
        {
            box.Password = "";
            box.PlaceholderText = cfg.TryGetValue($"{key}_CONFIGURED", out var value) && bool.TryParse(value?.ToString(), out var saved) && saved
                ? "Key saved · leave blank to keep it" : "Paste an API key";
        }
    }
    private void SetBusy(bool busy)
    {
        _busy = busy; SaveButton.IsEnabled = !busy; TestGroqButton.IsEnabled = !busy; TestOpenAiButton.IsEnabled = !busy;
        BusyRing.IsActive = busy; BusyRing.Visibility = busy ? Visibility.Visible : Visibility.Collapsed;
    }
    private async void Save_Click(object sender, RoutedEventArgs e)
    {
        if (_busy) return;
        var updates = new Dictionary<string, object>();
        if (!string.IsNullOrWhiteSpace(GroqApiKeyBox.Password)) updates["GROQ_API_KEY"] = GroqApiKeyBox.Password.Trim();
        if (!string.IsNullOrWhiteSpace(OpenAiApiKeyBox.Password)) updates["OPENAI_API_KEY"] = OpenAiApiKeyBox.Password.Trim();
        if (updates.Count == 0) { Show("Keys unchanged", "Paste a new key to replace a saved one.", InfoBarSeverity.Informational); return; }
        SetBusy(true);
        try
        {
            if (!await App.ApiService.UpdateConfigAsync(updates)) { Show("Couldn't save keys", App.ApiService.LastError, InfoBarSeverity.Error); return; }
            await LoadKeysAsync();
            Show("Keys saved", "Choose a cloud provider in Models or Meeting notes when you want to use it.", InfoBarSeverity.Success);
        }
        finally { SetBusy(false); }
    }
    private async void Test_Click(object sender, RoutedEventArgs e)
    {
        if (_busy || sender is not Button button) return;
        var groq = button.Tag?.ToString() == "groq";
        var key = (groq ? GroqApiKeyBox : OpenAiApiKeyBox).Password.Trim();
        if (key.Length == 0) { Show("Paste a new key", "Checks use the key in this field. Saved keys stay private.", InfoBarSeverity.Warning); return; }
        SetBusy(true);
        try
        {
            using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(15) };
            http.DefaultRequestHeaders.Authorization = new("Bearer", key);
            using var res = await http.GetAsync(groq ? "https://api.groq.com/openai/v1/models" : "https://api.openai.com/v1/models");
            Show(res.IsSuccessStatusCode ? "Key verified" : "Key check failed", res.IsSuccessStatusCode ? "This key can access the provider. Save it to use it in DisWhisper." : $"The provider returned HTTP {(int)res.StatusCode}. Check the key and account.", res.IsSuccessStatusCode ? InfoBarSeverity.Success : InfoBarSeverity.Error);
        }
        catch (Exception error) { Show("Connection failed", error.Message.Replace(key, "[credential]"), InfoBarSeverity.Error); }
        finally { SetBusy(false); }
    }
    private void Show(string title, string message, InfoBarSeverity severity) { Notice.Title = title; Notice.Message = message; Notice.Severity = severity; Notice.IsOpen = true; }
}
