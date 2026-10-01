using DisWhisper.Companion.Models;
using DisWhisper.Companion.Services;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Navigation;
using Windows.ApplicationModel.DataTransfer;

namespace DisWhisper.Companion.Views;

public partial class SummariesPage : Page
{
    private string? _filename;
    private bool _generating;
    public SummariesPage()
    {
        InitializeComponent();
        Motion.EnablePressFeedback(GenerateButton);
        Loaded += async (_, _) =>
        {
            var items = await App.ApiService.GetTranscriptsAsync();
            TranscriptSelector.ItemsSource = items;
            TranscriptSelector.SelectedItem = items.FirstOrDefault(t => t.Filename == _filename) ?? items.FirstOrDefault();
            if (!string.IsNullOrEmpty(App.ApiService.LastError)) Show("Couldn't load meetings", App.ApiService.LastError, InfoBarSeverity.Warning);
        };
    }
    protected override void OnNavigatedTo(NavigationEventArgs e) { _filename = e.Parameter as string; base.OnNavigatedTo(e); }
    private void Provider_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (PrivacyNote == null) return;
        PrivacyNote.Text = (ProviderSelector.SelectedItem as ComboBoxItem)?.Tag?.ToString() == "local"
            ? "Local notes require Ollama and a downloaded language model. Your transcript is processed on this PC."
            : "Generating notes sends this transcript to the selected cloud provider. Their usage charges and privacy terms apply.";
    }
    private async void Generate_Click(object sender, RoutedEventArgs e)
    {
        if (_generating) return;
        if (TranscriptSelector.SelectedItem is not TranscriptItem item) { Show("Choose a meeting", "Select a saved transcript first.", InfoBarSeverity.Warning); return; }
        _generating = true; GenerateButton.IsEnabled = false; TranscriptSelector.IsEnabled = false; ProviderSelector.IsEnabled = false;
        BusyRing.IsActive = true; BusyRing.Visibility = Visibility.Visible; Notice.IsOpen = false; CopyButton.IsEnabled = false;
        try
        {
            var text = await App.ApiService.ReadTranscriptAsync(item.Filename);
            if (text == null) { Show("Couldn't read the transcript", App.ApiService.LastError, InfoBarSeverity.Error); return; }
            if (string.IsNullOrWhiteSpace(text)) { Show("Empty transcript", "This meeting has no transcript text to summarize.", InfoBarSeverity.Warning); return; }
            var selected = (ProviderSelector.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "local";
            var config = await App.ApiService.GetConfigAsync();
            if (config == null) { Show("Local service unavailable", App.ApiService.LastError, InfoBarSeverity.Error); return; }
            var model = selected == "local" ? config.GetValueOrDefault("LOCAL_SUMMARIZER_MODEL")?.ToString() ?? "llama3.2:3b" : selected == "openai" ? "gpt-4o-mini" : "llama-3.3-70b-versatile";
            var summary = await App.ApiService.SummarizeTranscriptAsync(text, selected == "local" ? "local" : "cloud", model, selected == "local" ? null : selected);
            if (summary.StartsWith("Error:")) { Show("Couldn't generate notes", summary[6..].Trim(), InfoBarSeverity.Error); return; }
            ResultBox.Text = summary; CopyButton.IsEnabled = !string.IsNullOrWhiteSpace(summary);
            Show("Meeting notes ready", "Copy the notes to share or save them.", InfoBarSeverity.Success);
        }
        finally { _generating = false; GenerateButton.IsEnabled = true; TranscriptSelector.IsEnabled = true; ProviderSelector.IsEnabled = true; BusyRing.IsActive = false; BusyRing.Visibility = Visibility.Collapsed; }
    }
    private void Copy_Click(object sender, RoutedEventArgs e)
    { var data = new DataPackage(); data.SetText(ResultBox.Text); Clipboard.SetContent(data); Show("Copied", "Meeting notes are on the clipboard.", InfoBarSeverity.Success); }
    private void ProviderSetup_Click(object sender, RoutedEventArgs e) => (App.MainWindow as MainWindow)?.NavigateTo((ProviderSelector.SelectedItem as ComboBoxItem)?.Tag?.ToString() == "local" ? "models" : "cloud");
    private void Show(string title, string message, InfoBarSeverity severity) { Notice.Title = title; Notice.Message = message; Notice.Severity = severity; Notice.IsOpen = true; }
}
