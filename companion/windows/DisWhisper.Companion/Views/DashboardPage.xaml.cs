using System;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace DisWhisper.Companion.Views;

public partial class DashboardPage : Page
{
    private readonly DispatcherTimer _refreshTimer;

    public DashboardPage()
    {
        this.InitializeComponent();

        _refreshTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(3) };
        _refreshTimer.Tick += async (s, e) => await LoadStatusAsync();
        _refreshTimer.Start();

        this.Loaded += async (s, e) => await LoadStatusAsync();
    }

    private async System.Threading.Tasks.Task LoadStatusAsync()
    {
        var status = await App.ApiService.GetStatusAsync();
        if (status == null || status.Status == "offline")
        {
            BotStatusText.Text = "Offline / Bot Not Running";
            BotStatusText.Foreground = (Microsoft.UI.Xaml.Media.SolidColorBrush)App.Current.Resources["DisWhisperOrangeBrush"];
            VoiceChannelText.Text = "Launch DisWhisper backend on http://127.0.0.1:8765";
            return;
        }

        BotStatusText.Text = status.BotUser;
        BotStatusText.Foreground = (Microsoft.UI.Xaml.Media.SolidColorBrush)App.Current.Resources["DisWhisperGreenBrush"];
        VoiceChannelText.Text = status.VoiceConnected ? $"Connected: #{status.VoiceChannel}" : "Voice: Idle (Use /join in Discord)";
        UptimeText.Text = $"Uptime: {status.UptimeSeconds} seconds";

        EngineNameText.Text = status.EngineName;
        EngineDetailsText.Text = $"Model: {status.ModelName}";
        DeviceText.Text = $"Device: {status.Device.ToUpper()} ({status.ComputeType})";

        SpeakersText.Text = $"Active Speakers: {status.ActiveSpeakerBuffers}";
        QueueText.Text = $"Audio Queue: {status.QueueDepth} chunks";
        if (status.GpuMemory != null)
        {
            GpuText.Text = $"GPU VRAM: {status.GpuMemory.AllocatedMb}MB / {status.GpuMemory.ReservedMb}MB";
        }
        else
        {
            GpuText.Text = "GPU VRAM: N/A (CPU Mode)";
        }
    }

    private async void RefreshButton_Click(object sender, RoutedEventArgs e)
    {
        await LoadStatusAsync();
    }

    private async void ApplyEngine_Click(object sender, RoutedEventArgs e)
    {
        if (EngineSelector.SelectedItem is ComboBoxItem item && item.Tag != null)
        {
            var tag = item.Tag.ToString()!;
            var ok = await App.ApiService.SwitchEngineAsync(tag);
            if (ok)
            {
                EngineSwitchNotice.Text = $"✓ Successfully switched STT engine to {item.Content}";
                EngineSwitchNotice.Visibility = Visibility.Visible;
                await LoadStatusAsync();
            }
            else
            {
                EngineSwitchNotice.Text = "❌ Failed to switch engine. Ensure backend is running.";
                EngineSwitchNotice.Visibility = Visibility.Visible;
            }
        }
    }
}
