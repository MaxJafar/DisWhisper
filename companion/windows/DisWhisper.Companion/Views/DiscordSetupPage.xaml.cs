using System.Diagnostics;
using DisWhisper.Companion.Models;
using DisWhisper.Companion.Services;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace DisWhisper.Companion.Views;

public partial class DiscordSetupPage : Page
{
    private DiscordConnectionInfo? _connection;
    private string _selectedServerId = "";
    private bool _busy;

    public DiscordSetupPage()
    {
        InitializeComponent();
        TokenBox.PasswordChanged += (_, _) => { _connection = null; InviteButton.IsEnabled = false; BotName.Text = "Check your bot account"; };
        Motion.EnablePressFeedback(CheckButton); Motion.EnablePressFeedback(SaveButton);
        Loaded += async (_, _) =>
        {
            var config = await App.ApiService.GetConfigAsync();
            if (config == null) { Show("Local service is starting", "Try again in a moment, or retry the service from Home.", InfoBarSeverity.Warning); return; }
            _selectedServerId = config.TryGetValue("GUILD_ID", out var server) ? server?.ToString() ?? "" : "";
            TokenBox.Password = "";
            TokenBox.PlaceholderText = config.TryGetValue("DISCORD_TOKEN_CONFIGURED", out var flag) && bool.TryParse(flag?.ToString(), out var saved) && saved ? "Token saved · leave blank to keep it" : "Paste your bot token";
            if (config.TryGetValue("LANGUAGE", out var language))
                foreach (ComboBoxItem item in LanguageSelector.Items)
                    if (item.Tag?.ToString() == language?.ToString()) LanguageSelector.SelectedItem = item;
            if (App.ApiService.LatestStatus.Status == "online") Show("Your bot is connected", "Disconnect it from Home before switching bot accounts or servers.", InfoBarSeverity.Informational);
        };
    }

    private async void Check_Click(object sender, RoutedEventArgs e)
    {
        if (_busy) return;
        _busy = true; CheckButton.IsEnabled = false; CheckRing.IsActive = true; CheckRing.Visibility = Visibility.Visible;
        try
        {
            TokenBox.IsEnabled = false;
            _connection = await App.ApiService.ValidateDiscordAsync(TokenBox.Password);
            if (_connection == null) { Show("Couldn't check the bot", App.ApiService.LastError, InfoBarSeverity.Error); return; }
            BotName.Text = $"Connected as {_connection.BotName}";
            InviteButton.IsEnabled = true;
            ServerSelector.ItemsSource = _connection.Servers;
            ServerSelector.SelectedItem = _connection.Servers.FirstOrDefault(s => s.Id == _selectedServerId) ?? _connection.Servers.FirstOrDefault();
            Show(_connection.Servers.Count > 0 ? "Bot account verified" : "Invite your bot next", _connection.Servers.Count > 0 ? "Choose the server you want to transcribe." : "Use the invite button, then check the connection again.", InfoBarSeverity.Success);
        }
        finally { _busy = false; TokenBox.IsEnabled = true; CheckButton.IsEnabled = true; CheckRing.IsActive = false; CheckRing.Visibility = Visibility.Collapsed; }
    }

    private async void Save_Click(object sender, RoutedEventArgs e)
    {
        if (_busy) return;
        if (_connection == null) { Show("Check your bot first", "Use Check connection to verify this bot token.", InfoBarSeverity.Warning); return; }
        if (ServerSelector.SelectedItem is not DiscordServer server || !long.TryParse(server.Id, out var guildId)) { Show("Choose a server", "Invite your bot, then check the connection again to refresh the server list.", InfoBarSeverity.Warning); return; }
        _busy = true; SaveButton.IsEnabled = false; SaveRing.IsActive = true; SaveRing.Visibility = Visibility.Visible;
        try
        {
            var updates = new Dictionary<string, object> { ["GUILD_ID"] = guildId, ["LANGUAGE"] = (LanguageSelector.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "auto", ["AUTO_CONNECT_BOT"] = AutoConnectToggle.IsOn };
            if (!string.IsNullOrWhiteSpace(TokenBox.Password)) updates["DISCORD_TOKEN"] = TokenBox.Password.Trim();
            if (!await App.ApiService.UpdateConfigAsync(updates)) { Show("Couldn't save", App.ApiService.LastError, InfoBarSeverity.Error); return; }
            TokenBox.Password = "";
            _selectedServerId = server.Id;
            (App.MainWindow as MainWindow)?.NavigateTo("models");
        }
        finally { _busy = false; SaveButton.IsEnabled = true; SaveRing.IsActive = false; SaveRing.Visibility = Visibility.Collapsed; }
    }

    private void Portal_Click(object sender, RoutedEventArgs e) => Process.Start(new ProcessStartInfo("https://discord.com/developers/applications") { UseShellExecute = true });
    private void Invite_Click(object sender, RoutedEventArgs e)
    { if (_connection != null && Uri.TryCreate(_connection.InviteUrl, UriKind.Absolute, out var uri) && uri.Scheme == "https" && uri.Host == "discord.com") Process.Start(new ProcessStartInfo(uri.AbsoluteUri) { UseShellExecute = true }); }
    private void Show(string title, string message, InfoBarSeverity severity) { Notice.Title = title; Notice.Message = message; Notice.Severity = severity; Notice.IsOpen = true; }
}
