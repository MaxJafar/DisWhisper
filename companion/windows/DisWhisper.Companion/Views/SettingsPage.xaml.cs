using System;
using System.Collections.Generic;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace DisWhisper.Companion.Views;

public partial class SettingsPage : Page
{
    public SettingsPage()
    {
        this.InitializeComponent();
        this.Loaded += async (s, e) => await LoadSettingsAsync();
    }

    private async System.Threading.Tasks.Task LoadSettingsAsync()
    {
        var cfg = await App.ApiService.GetConfigAsync();
        if (cfg == null) return;

        if (cfg.TryGetValue("DISCORD_TOKEN", out var tok) && tok != null)
            TokenBox.Password = tok.ToString() ?? "";
        if (cfg.TryGetValue("GUILD_ID", out var gid) && gid != null)
            GuildIdBox.Text = gid.ToString() ?? "";
        if (cfg.TryGetValue("TRANSCRIPT_CHANNEL_NAME", out var ch) && ch != null)
            ChannelNameBox.Text = ch.ToString() ?? "live-transcript";

        if (cfg.TryGetValue("CHUNKING_DURATION_SEC", out var chunk) && double.TryParse(chunk?.ToString(), out var cVal))
        {
            ChunkDurationSlider.Value = cVal;
            ChunkDurationValue.Text = $"{cVal:F1}s";
        }

        if (cfg.TryGetValue("SILENCE_THRESHOLD", out var sil) && double.TryParse(sil?.ToString(), out var sVal))
        {
            SilenceSlider.Value = sVal;
            SilenceThresholdValue.Text = $"{sVal:F3}";
        }

        if (cfg.TryGetValue("CONTINUOUS_SPEECH_TIMEOUT_SEC", out var deb) && double.TryParse(deb?.ToString(), out var dVal))
        {
            DebounceSlider.Value = dVal;
            DebounceValue.Text = $"{dVal:F1}s";
        }

        if (cfg.TryGetValue("AUTO_SAVE_TRANSCRIPTS", out var auto) && bool.TryParse(auto?.ToString(), out var aVal))
        {
            AutoSaveToggle.IsOn = aVal;
        }
    }

    private void ChunkDurationSlider_ValueChanged(object sender, Microsoft.UI.Xaml.Controls.Primitives.RangeBaseValueChangedEventArgs e)
    {
        if (ChunkDurationValue != null)
            ChunkDurationValue.Text = $"{e.NewValue:F1}s";
    }

    private void SilenceSlider_ValueChanged(object sender, Microsoft.UI.Xaml.Controls.Primitives.RangeBaseValueChangedEventArgs e)
    {
        if (SilenceThresholdValue != null)
            SilenceThresholdValue.Text = $"{e.NewValue:F3}";
    }

    private void DebounceSlider_ValueChanged(object sender, Microsoft.UI.Xaml.Controls.Primitives.RangeBaseValueChangedEventArgs e)
    {
        if (DebounceValue != null)
            DebounceValue.Text = $"{e.NewValue:F1}s";
    }

    private async void SaveSettings_Click(object sender, RoutedEventArgs e)
    {
        var updates = new Dictionary<string, object>
        {
            ["DISCORD_TOKEN"] = TokenBox.Password,
            ["TRANSCRIPT_CHANNEL_NAME"] = ChannelNameBox.Text,
            ["CHUNKING_DURATION_SEC"] = ChunkDurationSlider.Value,
            ["SILENCE_THRESHOLD"] = SilenceSlider.Value,
            ["CONTINUOUS_SPEECH_TIMEOUT_SEC"] = DebounceSlider.Value,
            ["AUTO_SAVE_TRANSCRIPTS"] = AutoSaveToggle.IsOn,
        };

        if (long.TryParse(GuildIdBox.Text.Trim(), out var guildId))
        {
            updates["GUILD_ID"] = guildId;
        }

        var ok = await App.ApiService.UpdateConfigAsync(updates);
        var dialog = new ContentDialog
        {
            Title = ok ? "Settings Saved" : "Error",
            Content = ok ? "Audio and bot customization settings saved successfully!" : "Failed to update configuration on backend.",
            CloseButtonText = "OK",
            XamlRoot = this.XamlRoot
        };
        await dialog.ShowAsync();
    }
}
