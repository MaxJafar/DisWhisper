using System.Text.Json.Serialization;

namespace DisWhisper.Companion.Models;

public class DisWhisperStatus
{
    [JsonPropertyName("status")]
    public string Status { get; set; } = "offline";

    [JsonPropertyName("bot_user")]
    public string BotUser { get; set; } = "Disconnected";

    [JsonPropertyName("voice_connected")]
    public bool VoiceConnected { get; set; }

    [JsonPropertyName("voice_channel")]
    public string? VoiceChannel { get; set; }

    [JsonPropertyName("engine_name")]
    public string EngineName { get; set; } = "Whisper";

    [JsonPropertyName("model_name")]
    public string ModelName { get; set; } = "base";

    [JsonPropertyName("device")]
    public string Device { get; set; } = "cpu";

    [JsonPropertyName("compute_type")]
    public string ComputeType { get; set; } = "int8";

    [JsonPropertyName("queue_depth")]
    public int QueueDepth { get; set; }

    [JsonPropertyName("active_speaker_buffers")]
    public int ActiveSpeakerBuffers { get; set; }

    [JsonPropertyName("uptime_seconds")]
    public int UptimeSeconds { get; set; }

    [JsonPropertyName("gpu_memory")]
    public GpuMemoryInfo? GpuMemory { get; set; }
    [JsonPropertyName("engine_loaded")] public bool EngineLoaded { get; set; }
    [JsonPropertyName("error")] public string Error { get; set; } = "";
    [JsonPropertyName("token_configured")] public bool TokenConfigured { get; set; }
    [JsonPropertyName("managed")] public bool Managed { get; set; }
    [JsonPropertyName("language")] public string Language { get; set; } = "auto";
    [JsonPropertyName("session_id")] public string SessionId { get; set; } = "";
    [JsonPropertyName("process_id")] public int ProcessId { get; set; }
}

public class GpuMemoryInfo
{
    [JsonPropertyName("allocated_mb")]
    public double AllocatedMb { get; set; }

    [JsonPropertyName("reserved_mb")]
    public double ReservedMb { get; set; }
}
