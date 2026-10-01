using System.Diagnostics;
using System.Globalization;
using DisWhisper.Companion.Services;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace DisWhisper.Companion.Views;

public partial class SettingsPage : Page
{
    private bool _initializing = true;
    private bool _saving;

    public SettingsPage()
    {
        InitializeComponent();
        Motion.EnablePressFeedback(SaveButton);
        Loaded += async (_, _) =>
        {
            _initializing = true;
            Select(ThemeSelector, App.Preferences.Theme);
            MotionToggle.IsOn = App.Preferences.MotionEnabled;
            _initializing = false;
            var cfg = await App.ApiService.GetConfigAsync();
            if (cfg == null) { Show("Local service unavailable", App.ApiService.LastError, InfoBarSeverity.Warning); return; }
            string Value(string key, string fallback = "") => cfg.TryGetValue(key, out var value) ? value?.ToString() ?? fallback : fallback;
            bool Flag(string key, bool fallback) => bool.TryParse(Value(key), out var value) ? value : fallback;
            double Number(string key, double fallback) => double.TryParse(Value(key), CultureInfo.InvariantCulture, out var value) ? value : fallback;
            ChannelNameBox.Text = Value("TRANSCRIPT_CHANNEL_NAME", "live-transcript");
            LanguageBox.Text = Value("LANGUAGE", "auto");
            CudaFolderBox.Text = Value("CUDA_LIBRARY_DIR");
            Select(DeviceSelector, Value("DEVICE", "auto"));
            Select(PrecisionSelector, Value("COMPUTE_TYPE", "int8"));
            AutoCreateToggle.IsOn = Flag("AUTO_CREATE_TRANSCRIPT_CHANNEL", true);
            AutoPostToggle.IsOn = Flag("AUTO_POST_TRANSCRIPTS", true);
            AutoSaveToggle.IsOn = Flag("AUTO_SAVE_TRANSCRIPTS", true);
            AutoConnectToggle.IsOn = Flag("AUTO_CONNECT_BOT", false);
            EmptyChannelDelay.Value = Number("AUTO_LEAVE_EMPTY_SEC", 60);
            ChunkDuration.Value = Number("CHUNKING_DURATION_SEC", 2.5);
            SilenceThreshold.Value = Number("SILENCE_THRESHOLD", 0.01);
            Debounce.Value = Number("CONTINUOUS_SPEECH_TIMEOUT_SEC", 5);
        };
    }

    private static void Select(ComboBox box, string value)
    { foreach (ComboBoxItem item in box.Items) if (item.Tag?.ToString() == value) box.SelectedItem = item; }

    private void Appearance_Changed(object sender, SelectionChangedEventArgs e) => SaveAppearance();
    private void Motion_Changed(object sender, RoutedEventArgs e) => SaveAppearance();
    private void SaveAppearance()
    {
        if (_initializing) return;
        App.Preferences.Theme = (ThemeSelector.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "system";
        App.Preferences.MotionEnabled = MotionToggle.IsOn;
        if (App.MainWindow?.Content is FrameworkElement root) App.Preferences.Apply(root);
        try { App.Preferences.Save(); }
        catch (Exception error) { Show("Couldn't save appearance", error.Message, InfoBarSeverity.Error); }
    }

    private async void Save_Click(object sender, RoutedEventArgs e)
    {
        if (_saving) return;
        if (new[] { EmptyChannelDelay.Value, ChunkDuration.Value, SilenceThreshold.Value, Debounce.Value }.Any(double.IsNaN))
        { Show("Check the numbers", "Fill in each audio setting before saving.", InfoBarSeverity.Warning); return; }
        _saving = true; SaveButton.IsEnabled = false; BusyRing.IsActive = true; BusyRing.Visibility = Visibility.Visible;
        try
        {
            var updates = new Dictionary<string, object>
            {
                ["TRANSCRIPT_CHANNEL_NAME"] = ChannelNameBox.Text.Trim(),
                ["LANGUAGE"] = LanguageBox.Text.Trim(),
                ["DEVICE"] = (DeviceSelector.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "auto",
                ["COMPUTE_TYPE"] = (PrecisionSelector.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "int8",
                ["CUDA_LIBRARY_DIR"] = string.IsNullOrWhiteSpace(CudaFolderBox.Text) ? null! : CudaFolderBox.Text.Trim(),
                ["AUTO_CREATE_TRANSCRIPT_CHANNEL"] = AutoCreateToggle.IsOn,
                ["AUTO_POST_TRANSCRIPTS"] = AutoPostToggle.IsOn,
                ["AUTO_SAVE_TRANSCRIPTS"] = AutoSaveToggle.IsOn,
                ["AUTO_CONNECT_BOT"] = AutoConnectToggle.IsOn,
                ["AUTO_LEAVE_EMPTY_SEC"] = EmptyChannelDelay.Value,
                ["CHUNKING_DURATION_SEC"] = ChunkDuration.Value,
                ["SILENCE_THRESHOLD"] = SilenceThreshold.Value,
                ["CONTINUOUS_SPEECH_TIMEOUT_SEC"] = Debounce.Value,
            };
            var ok = await App.ApiService.UpdateConfigAsync(updates);
            Show(ok ? "Settings saved" : "Couldn't save settings", ok ? "Your next audio chunks use these settings." : App.ApiService.LastError, ok ? InfoBarSeverity.Success : InfoBarSeverity.Error);
        }
        finally { _saving = false; SaveButton.IsEnabled = true; BusyRing.IsActive = false; BusyRing.Visibility = Visibility.Collapsed; }
    }
    private void OpenData_Click(object sender, RoutedEventArgs e) => Process.Start(new ProcessStartInfo(App.BackendService.DataDirectory) { UseShellExecute = true });
    private void Discord_Click(object sender, RoutedEventArgs e) => (App.MainWindow as MainWindow)?.NavigateTo("discord");
    private void Show(string title, string message, InfoBarSeverity severity) { Notice.Title = title; Notice.Message = message; Notice.Severity = severity; Notice.IsOpen = true; }
}
