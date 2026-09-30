using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Net.Http;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace DisWhisper.Companion.Views;

public partial class CloudProvidersPage : Page
{
    public CloudProvidersPage()
    {
        this.InitializeComponent();
        this.Loaded += async (s, e) => await LoadExistingKeysAsync();
    }

    private async System.Threading.Tasks.Task LoadExistingKeysAsync()
    {
        var cfg = await App.ApiService.GetConfigAsync();
        if (cfg != null)
        {
            if (cfg.TryGetValue("GROQ_API_KEY", out var groq) && groq != null)
                GroqApiKeyBox.Password = groq.ToString() ?? "";
            if (cfg.TryGetValue("OPENAI_API_KEY", out var oai) && oai != null)
                OpenAiApiKeyBox.Password = oai.ToString() ?? "";
            if (cfg.TryGetValue("GEMINI_API_KEY", out var gem) && gem != null)
                GeminiApiKeyBox.Password = gem.ToString() ?? "";
        }
    }

    private async void SaveKeys_Click(object sender, RoutedEventArgs e)
    {
        var updates = new Dictionary<string, object>
        {
            ["GROQ_API_KEY"] = GroqApiKeyBox.Password,
            ["OPENAI_API_KEY"] = OpenAiApiKeyBox.Password,
            ["GEMINI_API_KEY"] = GeminiApiKeyBox.Password,
        };

        var ok = await App.ApiService.UpdateConfigAsync(updates);
        var dialog = new ContentDialog
        {
            Title = ok ? "Saved" : "Save Failed",
            Content = ok ? "Cloud API keys saved and synchronized with DisWhisper backend." : "Could not reach DisWhisper backend.",
            CloseButtonText = "OK",
            XamlRoot = this.XamlRoot
        };
        await dialog.ShowAsync();
    }

    private async void TestGroq_Click(object sender, RoutedEventArgs e)
    {
        var key = GroqApiKeyBox.Password;
        if (string.IsNullOrWhiteSpace(key))
        {
            ShowDialog("Error", "Please enter a Groq API key first.");
            return;
        }

        try
        {
            using var http = new HttpClient();
            http.DefaultRequestHeaders.Add("Authorization", $"Bearer {key}");
            var res = await http.GetAsync("https://api.groq.com/openai/v1/models");
            ShowDialog(res.IsSuccessStatusCode ? "Groq Validated" : "Groq Error",
                res.IsSuccessStatusCode ? "✓ Successfully connected to Groq Cloud API!" : $"HTTP {res.StatusCode}");
        }
        catch (Exception ex)
        {
            ShowDialog("Connection Error", ex.Message);
        }
    }

    private async void TestOpenAi_Click(object sender, RoutedEventArgs e)
    {
        var key = OpenAiApiKeyBox.Password;
        if (string.IsNullOrWhiteSpace(key))
        {
            ShowDialog("Error", "Please enter an OpenAI API key first.");
            return;
        }

        try
        {
            using var http = new HttpClient();
            http.DefaultRequestHeaders.Add("Authorization", $"Bearer {key}");
            var res = await http.GetAsync("https://api.openai.com/v1/models");
            ShowDialog(res.IsSuccessStatusCode ? "OpenAI Validated" : "OpenAI Error",
                res.IsSuccessStatusCode ? "✓ Successfully connected to OpenAI API!" : $"HTTP {res.StatusCode}");
        }
        catch (Exception ex)
        {
            ShowDialog("Connection Error", ex.Message);
        }
    }

    private async void TestGemini_Click(object sender, RoutedEventArgs e)
    {
        var key = GeminiApiKeyBox.Password;
        if (string.IsNullOrWhiteSpace(key))
        {
            ShowDialog("Error", "Please enter a Gemini API key first.");
            return;
        }

        try
        {
            using var http = new HttpClient();
            var res = await http.GetAsync($"https://generativelanguage.googleapis.com/v1beta/models?key={key}");
            ShowDialog(res.IsSuccessStatusCode ? "Gemini Validated" : "Gemini Error",
                res.IsSuccessStatusCode ? "✓ Successfully connected to Google Gemini API!" : $"HTTP {res.StatusCode}");
        }
        catch (Exception ex)
        {
            ShowDialog("Connection Error", ex.Message);
        }
    }

    private async void ShowDialog(string title, string content)
    {
        var dialog = new ContentDialog
        {
            Title = title,
            Content = content,
            CloseButtonText = "OK",
            XamlRoot = this.XamlRoot
        };
        await dialog.ShowAsync();
    }

    private void OpenGroqConsole_Click(object sender, RoutedEventArgs e) =>
        Process.Start(new ProcessStartInfo { FileName = "https://console.groq.com/keys", UseShellExecute = true });

    private void OpenOpenAiConsole_Click(object sender, RoutedEventArgs e) =>
        Process.Start(new ProcessStartInfo { FileName = "https://platform.openai.com/api-keys", UseShellExecute = true });

    private void OpenGeminiConsole_Click(object sender, RoutedEventArgs e) =>
        Process.Start(new ProcessStartInfo { FileName = "https://aistudio.google.com/app/apikey", UseShellExecute = true });
}
