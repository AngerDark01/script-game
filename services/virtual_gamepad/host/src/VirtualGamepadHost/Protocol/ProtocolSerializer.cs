using System.Text.Json;
using System.Text.Json.Serialization;

namespace VirtualGamepadHost.Protocol;

public static class ProtocolSerializer
{
    public static readonly JsonSerializerOptions Options = new(JsonSerializerDefaults.Web)
    {
        Converters = { new JsonStringEnumConverter(JsonNamingPolicy.CamelCase) },
    };

    public static MessageEnvelope Parse(string line)
    {
        using var document = JsonDocument.Parse(line);
        var root = document.RootElement;
        if (root.ValueKind != JsonValueKind.Object)
        {
            throw new JsonException("Protocol message must be a JSON object.");
        }

        var type = root.TryGetProperty("type", out var typeElement)
            ? typeElement.GetString()
            : null;
        if (string.IsNullOrWhiteSpace(type))
        {
            throw new JsonException("Protocol message requires a type.");
        }

        var id = root.TryGetProperty("id", out var idElement) ? idElement.GetString() : null;
        var payload = root.TryGetProperty("payload", out var payloadElement)
            ? payloadElement.Clone()
            : JsonDocument.Parse("{}").RootElement.Clone();
        return new MessageEnvelope(id, type, payload);
    }

    public static string Success(string? id, object? payload = null)
    {
        return JsonSerializer.Serialize(new
        {
            id,
            ok = true,
            payload = payload ?? new { },
        }, Options);
    }

    public static string Failure(string? id, string code, string message)
    {
        return JsonSerializer.Serialize(new
        {
            id,
            ok = false,
            error = new ProtocolError(code, message),
        }, Options);
    }

    public static string Event(string type, object payload)
    {
        return JsonSerializer.Serialize(new { type, payload }, Options);
    }
}
