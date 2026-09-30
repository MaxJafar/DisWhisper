using System;
using System.IO;
using System.Threading.Tasks;
using Windows.ApplicationModel.DataTransfer;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using DisWhisper.Companion.Models;

namespace DisWhisper.Companion.Views;

public partial class SummariesPage : Page
{
    public SummariesPage()
    {
        this.InitializeComponent();
        this.Loaded += async (s, e) => await LoadTranscriptsListAsync();
    }

    private async Task LoadTranscriptsListAsync()
    {
        var items = await App.ApiService.GetTranscriptsAsync();
        TranscriptSelector.Items.Clear();

        foreach (var item in items)
        {
            TranscriptSelector.Items.Add(new ComboBoxItem
            {
                Content = $"{item.Filename} ({item.SizeBytes / 1024} KB)",
                Tag = item.Path
            });
        }

        if (TranscriptSelector.Items.Count > 0)
        {
            TranscriptSelector.SelectedIndex = 0;
        }
    }

    private async void GenerateSummary_Click(object sender, RoutedEventArgs e)
    {
        if (TranscriptSelector.SelectedItem is not ComboBoxItem selected || selected.Tag == null)
        {
            SummaryResultBox.Text = "Please select a meeting transcript from the list above first.";
            return;
        }

        var filePath = selected.Tag.ToString()!;
        if (!File.Exists(filePath))
        {
            SummaryResultBox.Text = $"File not found at: {filePath}";
            return;
        }

        string transcriptText = await File.ReadAllTextAsync(filePath);
        if (string.IsNullOrWhiteSpace(transcriptText))
        {
            SummaryResultBox.Text = "Selected transcript is empty.";
            return;
        }

        var provider = "cloud";
        string? model = null;
        if (SummarizerProviderBox.SelectedItem is ComboBoxItem pItem && pItem.Tag != null)
        {
            var pTag = pItem.Tag.ToString()!;
            if (pTag == "local")
            {
                provider = "local";
                model = "llama3.2";
            }
            else if (pTag == "openai")
            {
                provider = "cloud";
                model = "gpt-4o-mini";
            }
            else
            {
                provider = "cloud";
                model = "llama-3.3-70b-versatile";
            }
        }

        LoadingPanel.Visibility = Visibility.Visible;
        SummaryResultBox.Text = "Analyzing audio utterances and synthesizing agenda, decisions, and action items...";

        try
        {
            var summary = await App.ApiService.SummarizeTranscriptAsync(transcriptText, provider, model);
            SummaryResultBox.Text = summary;
        }
        catch (Exception ex)
        {
            SummaryResultBox.Text = $"Failed to generate summary: {ex.Message}";
        }
        finally
        {
            LoadingPanel.Visibility = Visibility.Collapsed;
        }
    }

    private void CopySummary_Click(object sender, RoutedEventArgs e)
    {
        if (!string.IsNullOrWhiteSpace(SummaryResultBox.Text))
        {
            var pkg = new DataPackage();
            pkg.SetText(SummaryResultBox.Text);
            Clipboard.SetContent(pkg);
        }
    }
}
