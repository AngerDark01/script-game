using System.Text.Json;

namespace VirtualGamepadHost.Protocol;

public sealed record MessageEnvelope(string? Id, string Type, JsonElement Payload);

public sealed record ProtocolError(string Code, string Message);
