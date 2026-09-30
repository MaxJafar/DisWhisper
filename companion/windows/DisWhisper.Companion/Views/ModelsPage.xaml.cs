using System;
using System.Diagnostics;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace DisWhisper.Companion.Views;

public partial class ModelsPage : Page
{
    public ModelsPage()
    {
        this.InitializeComponent();

        App.ApiService.OnEventReceived += (eventName, data) =>
        {
            if (eventName == "download_progress")
            {
                this.DispatcherQueue.TryEnqueue(() =>
                {
                    if (data.TryGetProperty("percent", out var pct))
                    {
                        DownloadProgressPanel.Visibility = Visibility.Visible;
                        ModelProgressBar.Value = pct.GetInt32();
                        DownloadStatusLabel.Text = $"Downloading {data.GetProperty("model_id").GetString()} ({pct.GetInt32()}%)...";

                        if (pct.GetInt32() >= 100)
                        {
                            DownloadStatusLabel.Text = "✓ Download complete!";
                        }
                    }
                });
            }
        };
    }

    private async void ActivateEngine_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button btn && btn.Tag != null)
        {
            var engineTag = btn.Tag.ToString()!;
            var ok = await App.ApiService.SwitchEngineAsync(engineTag);
            var dialog = new ContentDialog
            {
                Title = ok ? "Engine Switched" : "Failed to Switch",
                Content = ok ? $"Successfully activated {engineTag}!" : "Error communicating with backend.",
                CloseButtonText = "OK",
                XamlRoot = this.XamlRoot
            };
            await dialog.ShowAsync();
        }
    }

    private async void DownloadModel_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button btn && btn.Tag != null)
        {
            var modelTag = btn.Tag.ToString()!;
            DownloadProgressPanel.Visibility = Visibility.Visible;
            ModelProgressBar.Value = 10;
            DownloadStatusLabel.Text = $"Starting background download for {modelTag}...";

            await App.ApiService.DownloadModelAsync(modelTag);
        }
    }

    private async void TestOllama_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            using var http = new System.Net.Http.HttpClient { Timeout = TimeSpan.FromSeconds(3) };
            var res = await http.GetAsync("http://localhost:11434/api/tags");
            var dialog = new ContentDialog
            {
                Title = res.IsSuccessStatusCode ? "Ollama Online" : "Ollama Offline",
                Content = res.IsSuccessStatusCode
                    ? "Successfully reached Ollama on http://localhost:11434!"
                    : $"Ollama responded with HTTP {res.StatusCode}.",
                CloseButtonText = "OK",
                XamlRoot = this.XamlRoot
            };
            await dialog.ShowAsync();
        }
        catch (Exception ex)
        {
            var dialog = new ContentDialog
            {
                Title = "Ollama Unreachable",
                Content = $"Could not connect to Ollama: {ex.Message}\nMake sure Ollama is installed and running (`ollama serve`).",
                CloseButtonText = "OK",
                XamlRoot = this.XamlRoot
            };
            await dialog.ShowAsync();
        }
    }

    private void OpenOllamaSite_Click(object sender, RoutedEventArgs e)
    {
        Process.Start(new ProcessStartInfo
        {
            FileName = "https://ollama.com",
            UseShellExecute = true
        });
    }
}
