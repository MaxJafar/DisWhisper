using System.Diagnostics;
using System.Text.RegularExpressions;
using DisWhisper.Companion.Models;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Documents;
using Windows.ApplicationModel.DataTransfer;

namespace DisWhisper.Companion.Views;

public partial class TranscriptsPage : Page
{
    private List<TranscriptItem> _items = new();
    private TranscriptItem? _selected;
    private string _content = "";
    private bool _refreshing;
    private int _selectionVersion;

    public TranscriptsPage() { InitializeComponent(); Loaded += async (_, _) => await RefreshAsync(); }

    private async Task RefreshAsync()
    {
        if (_refreshing) return;
        _refreshing = true;
        try
        {
            _items = await App.ApiService.GetTranscriptsAsync(); Filter();
            if (!string.IsNullOrEmpty(App.ApiService.LastError)) { Notice.Title = "Couldn't load meetings"; Notice.Message = App.ApiService.LastError; Notice.Severity = InfoBarSeverity.Warning; Notice.IsOpen = true; }
        }
        finally { _refreshing = false; }
    }

    private void Filter()
    {
        var query = SearchBox.Text.Trim();
        var filename = _selected?.Filename;
        var filtered = _items.Where(item => (item.Filename + " " + item.Title).Contains(query, StringComparison.OrdinalIgnoreCase)).ToList();
        TranscriptList.ItemsSource = filtered;
        if (filename != null) TranscriptList.SelectedItem = filtered.FirstOrDefault(item => item.Filename == filename);
    }

    private async void Transcript_Selected(object sender, SelectionChangedEventArgs e)
    {
        _selected = TranscriptList.SelectedItem as TranscriptItem;
        var version = ++_selectionVersion;
        CopyButton.IsEnabled = OpenButton.IsEnabled = NotesButton.IsEnabled = false;
        Preview.Blocks.Clear(); _content = ""; Preview.Visibility = Visibility.Collapsed; EmptyState.Visibility = Visibility.Visible;
        if (_selected == null) { Preview.Visibility = Visibility.Collapsed; EmptyState.Visibility = Visibility.Visible; return; }
        PreviewTitle.Text = _selected.Title;
        var content = await App.ApiService.ReadTranscriptAsync(_selected.Filename);
        if (version != _selectionVersion) return;
        if (content == null) { Notice.Title = "Couldn't open transcript"; Notice.Message = App.ApiService.LastError; Notice.Severity = InfoBarSeverity.Error; Notice.IsOpen = true; return; }
        _content = content;
        Preview.Blocks.Clear();
        foreach (var line in content.Split('\n'))
        {
            if (string.IsNullOrWhiteSpace(line)) continue;
            var paragraph = new Paragraph { Margin = new Thickness(0, 0, 0, 12) };
            if (line.StartsWith('#')) { paragraph.Inlines.Add(new Bold { Inlines = { new Run { Text = line.TrimStart('#', ' ').TrimEnd('\r') } } }); paragraph.FontSize = line.StartsWith("# ") ? 21 : 16; }
            else
            {
                var match = Regex.Match(line, @"^\*\*(.+?):\*\*\s*(.*)");
                if (match.Success) { paragraph.Inlines.Add(new Bold { Inlines = { new Run { Text = match.Groups[1].Value + ": " } } }); paragraph.Inlines.Add(new Run { Text = match.Groups[2].Value }); }
                else paragraph.Inlines.Add(new Run { Text = line.Replace("**", "").TrimEnd('\r') });
            }
            Preview.Blocks.Add(paragraph);
        }
        EmptyState.Visibility = Visibility.Collapsed; Preview.Visibility = Visibility.Visible;
        CopyButton.IsEnabled = OpenButton.IsEnabled = NotesButton.IsEnabled = true;
    }

    private void Search_Changed(AutoSuggestBox sender, AutoSuggestBoxTextChangedEventArgs args) { if (args.Reason == AutoSuggestionBoxTextChangeReason.UserInput) Filter(); }
    private async void Refresh_Click(object sender, RoutedEventArgs e) => await RefreshAsync();
    private void Copy_Click(object sender, RoutedEventArgs e) { var data = new DataPackage(); data.SetText(_content); Clipboard.SetContent(data); }
    private void Open_Click(object sender, RoutedEventArgs e) { if (_selected != null && File.Exists(_selected.Path)) Process.Start(new ProcessStartInfo(_selected.Path) { UseShellExecute = true }); }
    private void Notes_Click(object sender, RoutedEventArgs e) { if (_selected != null) (App.MainWindow as MainWindow)?.NavigateTo("summaries", _selected.Filename); }
    private async void Folder_Click(object sender, RoutedEventArgs e)
    {
        var directory = await App.ApiService.GetTranscriptDirectoryAsync();
        if (directory != null && Directory.Exists(directory)) Process.Start(new ProcessStartInfo(directory) { UseShellExecute = true });
        else { Notice.Title = "Folder unavailable"; Notice.Message = App.ApiService.LastError; Notice.IsOpen = true; }
    }
}
