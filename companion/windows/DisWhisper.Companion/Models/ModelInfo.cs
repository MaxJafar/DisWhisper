using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;
using CommunityToolkit.Mvvm.ComponentModel;
using Microsoft.UI.Xaml;

namespace DisWhisper.Companion.Models;

public class ModelInfo : ObservableObject
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("category")] public string Category { get; set; } = "";
    [JsonPropertyName("engine")] public string Engine { get; set; } = "";
    [JsonPropertyName("model_name")] public string ModelName { get; set; } = "";
    [JsonPropertyName("description")] public string Description { get; set; } = "";
    [JsonPropertyName("size_mb")] public int SizeMb { get; set; }
    [JsonPropertyName("languages")] public List<string> Languages { get; set; } = new();
    [JsonPropertyName("downloaded")] public bool Downloaded { get; set; }
    [JsonPropertyName("downloadable")] public bool Downloadable { get; set; }
    [JsonPropertyName("available")] public bool Available { get; set; } = true;
    [JsonPropertyName("active")] public bool Active { get; set; }
    [JsonPropertyName("source_url")] public string SourceUrl { get; set; } = "";

    private string _downloadStatus = "";
    private int? _progress;
    private string _detail = "";
    private string _error = "";

    public void SetProgress(string status, int? progress, string detail, string error)
    {
        _downloadStatus = status;
        _progress = progress;
        _detail = detail;
        _error = error;
        if (status == "completed") Downloaded = true;
        foreach (var property in new[] { nameof(StatusText), nameof(CanDownload), nameof(CanActivate),
            nameof(ProgressVisibility), nameof(IsIndeterminate), nameof(ProgressValue), nameof(DownloadLabel) })
            OnPropertyChanged(property);
    }

    [JsonIgnore] public bool CanDownload => Downloadable && Available && !Downloaded && _downloadStatus != "downloading";
    [JsonIgnore] public bool CanActivate => Downloaded && Available && !Active && _downloadStatus != "downloading";
    [JsonIgnore] public string DownloadLabel => Downloaded ? "Installed" : "Download";
    [JsonIgnore] public string ActivationLabel => Active ? "Selected" : Category == "local_llm" ? "Use for notes" : "Use model";
    [JsonIgnore] public string Details => $"{string.Join(", ", Languages)} · {(SizeMb == 0 ? "Cloud API" : $"~{SizeMb:N0} MB download")}";
    [JsonIgnore] public Visibility DownloadVisibility => Downloadable ? Visibility.Visible : Visibility.Collapsed;
    [JsonIgnore] public Visibility RecommendedVisibility => Id == "whisper-base" ? Visibility.Visible : Visibility.Collapsed;
    [JsonIgnore] public Visibility ProgressVisibility => _downloadStatus == "downloading" ? Visibility.Visible : Visibility.Collapsed;
    [JsonIgnore] public bool IsIndeterminate => !_progress.HasValue;
    [JsonIgnore] public double ProgressValue => _progress ?? 0;
    [JsonIgnore] public string StatusText => _downloadStatus switch
    {
        "failed" => $"Download failed: {_error}",
        "cancelled" => "Download interrupted. Retry to resume.",
        "downloading" => $"{_detail}{(_progress.HasValue ? $" ({_progress}%)" : "…")}",
        _ => !Available ? "Ollama is offline. Start Ollama, then refresh."
            : Active ? Downloaded ? "Selected model" : "Selected · download to begin" : Downloaded ? (Downloadable ? "Installed" : "API key configured")
            : Downloadable ? "Ready to download" : "Configure an API key in Cloud Providers",
    };
}

public class ModelsResponse
{
    [JsonPropertyName("models")] public List<ModelInfo> Models { get; set; } = new();
}

public class DownloadProgress
{
    [JsonPropertyName("status")] public string Status { get; set; } = "";
    [JsonPropertyName("percent")] public int? Percent { get; set; }
    [JsonPropertyName("detail")] public string Detail { get; set; } = "";
    [JsonPropertyName("error")] public string Error { get; set; } = "";
}

public class TranscriptItem
{
    [JsonPropertyName("filename")] public string Filename { get; set; } = "";
    [JsonPropertyName("path")] public string Path { get; set; } = "";
    [JsonPropertyName("size_bytes")] public long SizeBytes { get; set; }
    [JsonPropertyName("modified")] public string Modified { get; set; } = "";
    [JsonIgnore] public string Title => DateTime.TryParse(Modified, out var time) ? time.ToString("MMM d · HH:mm") : Filename;
    [JsonIgnore] public string Caption => $"Markdown · {Math.Max(1, SizeBytes / 1024):N0} KB";
}
