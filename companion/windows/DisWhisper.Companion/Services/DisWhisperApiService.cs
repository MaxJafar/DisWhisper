using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using DisWhisper.Companion.Models;

namespace DisWhisper.Companion.Services;

public class DisWhisperApiService
{
    private readonly HttpClient _httpClient;
    private readonly string _baseUrl;
    private ClientWebSocket? _webSocket;
    private CancellationTokenSource? _wsCts;

    public event Action<string, JsonElement>? OnEventReceived;

    public DisWhisperApiService(string baseUrl = "http://127.0.0.1:8765")
    {
        _baseUrl = baseUrl.TrimEnd('/');
        _httpClient = new HttpClient { Timeout = TimeSpan.FromSeconds(15) };
    }

    public async Task<DisWhisperStatus?> GetStatusAsync()
    {
        try
        {
            var res = await _httpClient.GetStringAsync($"{_baseUrl}/api/status");
            return JsonSerializer.Deserialize<DisWhisperStatus>(res);
        }
        catch
        {
            return new DisWhisperStatus { Status = "offline" };
        }
    }

    public async Task<Dictionary<string, object>?> GetConfigAsync()
    {
        try
        {
            var res = await _httpClient.GetStringAsync($"{_baseUrl}/api/config");
            return JsonSerializer.Deserialize<Dictionary<string, object>>(res);
        }
        catch
        {
            return null;
        }
    }

    public async Task<bool> UpdateConfigAsync(Dictionary<string, object> newConfig)
    {
        try
        {
            var json = JsonSerializer.Serialize(newConfig);
            var content = new StringContent(json, Encoding.UTF8, "application/json");
            var res = await _httpClient.PostAsync($"{_baseUrl}/api/config", content);
            return res.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    public async Task<List<ModelInfo>> GetModelsAsync()
    {
        try
        {
            var res = await _httpClient.GetStringAsync($"{_baseUrl}/api/models");
            var parsed = JsonSerializer.Deserialize<ModelsResponse>(res);
            return parsed?.Models ?? new List<ModelInfo>();
        }
        catch
        {
            return new List<ModelInfo>();
        }
    }

    public async Task<bool> DownloadModelAsync(string modelId)
    {
        try
        {
            var payload = JsonSerializer.Serialize(new { model_id = modelId });
            var content = new StringContent(payload, Encoding.UTF8, "application/json");
            var res = await _httpClient.PostAsync($"{_baseUrl}/api/models/download", content);
            return res.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    public async Task<bool> SwitchEngineAsync(string engine)
    {
        try
        {
            var payload = JsonSerializer.Serialize(new { engine = engine });
            var content = new StringContent(payload, Encoding.UTF8, "application/json");
            var res = await _httpClient.PostAsync($"{_baseUrl}/api/engine/switch", content);
            return res.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    public async Task<string> SummarizeTranscriptAsync(string transcriptText, string provider = "cloud", string? model = null)
    {
        try
        {
            var payload = JsonSerializer.Serialize(new
            {
                transcript_text = transcriptText,
                provider = provider,
                model = model
            });
            var content = new StringContent(payload, Encoding.UTF8, "application/json");
            var res = await _httpClient.PostAsync($"{_baseUrl}/api/summarize", content);
            if (res.IsSuccessStatusCode)
            {
                var body = await res.Content.ReadAsStringAsync();
                using var doc = JsonDocument.Parse(body);
                return doc.RootElement.GetProperty("summary").GetString() ?? "";
            }
            return $"Error: HTTP {res.StatusCode}";
        }
        catch (Exception ex)
        {
            return $"Error: {ex.Message}";
        }
    }

    public async Task<List<TranscriptItem>> GetTranscriptsAsync()
    {
        try
        {
            var res = await _httpClient.GetStringAsync($"{_baseUrl}/api/transcripts");
            using var doc = JsonDocument.Parse(res);
            if (doc.RootElement.TryGetProperty("transcripts", out var arr))
            {
                return JsonSerializer.Deserialize<List<TranscriptItem>>(arr.GetRawText()) ?? new List<TranscriptItem>();
            }
            return new List<TranscriptItem>();
        }
        catch
        {
            return new List<TranscriptItem>();
        }
    }

    public void StartWebSocketListener()
    {
        _wsCts?.Cancel();
        _wsCts = new CancellationTokenSource();
        Task.Run(() => ListenWebSocketLoop(_wsCts.Token));
    }

    private async Task ListenWebSocketLoop(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try
            {
                _webSocket = new ClientWebSocket();
                var wsUri = new Uri(_baseUrl.Replace("http://", "ws://") + "/api/events");
                await _webSocket.ConnectAsync(wsUri, ct);

                var buffer = new byte[8192];
                while (_webSocket.State == WebSocketState.Open && !ct.IsCancellationRequested)
                {
                    var result = await _webSocket.ReceiveAsync(new ArraySegment<byte>(buffer), ct);
                    if (result.MessageType == WebSocketMessageType.Close)
                    {
                        await _webSocket.CloseAsync(WebSocketCloseStatus.NormalClosure, "Closing", ct);
                        break;
                    }

                    var message = Encoding.UTF8.GetString(buffer, 0, result.Count);
                    using var doc = JsonDocument.Parse(message);
                    if (doc.RootElement.TryGetProperty("event", out var ev) &&
                        doc.RootElement.TryGetProperty("data", out var data))
                    {
                        OnEventReceived?.Invoke(ev.GetString() ?? "", data.Clone());
                    }
                }
            }
            catch
            {
                // Reconnect retry delay
                await Task.Delay(3000, ct);
            }
        }
    }
}
