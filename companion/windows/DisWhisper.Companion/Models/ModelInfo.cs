using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace DisWhisper.Companion.Models;

public class ModelInfo
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("category")]
    public string Category { get; set; } = string.Empty;

    [JsonPropertyName("latency")]
    public string Latency { get; set; } = string.Empty;

    [JsonPropertyName("size_mb")]
    public int SizeMb { get; set; }

    [JsonPropertyName("features")]
    public List<string> Features { get; set; } = new();

    [JsonPropertyName("languages")]
    public List<string> Languages { get; set; } = new();

    [JsonPropertyName("downloaded")]
    public bool Downloaded { get; set; }

    [JsonIgnore]
    public bool IsDownloading { get; set; }

    [JsonIgnore]
    public int DownloadProgress { get; set; }
}

public class ModelsResponse
{
    [JsonPropertyName("models")]
    public List<ModelInfo> Models { get; set; } = new();
}

public class TranscriptItem
{
    [JsonPropertyName("filename")]
    public string Filename { get; set; } = string.Empty;

    [JsonPropertyName("path")]
    public string Path { get; set; } = string.Empty;

    [JsonPropertyName("size_bytes")]
    public long SizeBytes { get; set; }

    [JsonPropertyName("modified")]
    public string Modified { get; set; } = string.Empty;
}
