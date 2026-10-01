using System.Text.Json.Serialization;

namespace DisWhisper.Companion.Models;

public sealed class DiscordConnectionInfo
{
    [JsonPropertyName("application_id")] public string ApplicationId { get; set; } = "";
    [JsonPropertyName("bot_id")] public string BotId { get; set; } = "";
    [JsonPropertyName("bot_name")] public string BotName { get; set; } = "";
    [JsonPropertyName("invite_url")] public string InviteUrl { get; set; } = "";
    [JsonPropertyName("servers")] public List<DiscordServer> Servers { get; set; } = new();
}

public sealed class DiscordServer
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    public override string ToString() => Name;
}
