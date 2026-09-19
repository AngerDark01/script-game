namespace LanInputSync;

[Flags]
internal enum SessionCapability
{
    None = 0,
    InputSend = 1 << 0,
    InputReceive = 1 << 1,
    PositionPublish = 1 << 2,
    PositionSubscribe = 1 << 3,
    EventPublish = 1 << 4,
    EventSubscribe = 1 << 5,
    CatalogPublish = 1 << 6,
    CatalogSubscribe = 1 << 7,
    MapPublish = 1 << 8,
    MapSubscribe = 1 << 9
}

internal static class SessionCapabilities
{
    public static SessionCapability DataSharing =>
        SessionCapability.PositionPublish | SessionCapability.PositionSubscribe
        | SessionCapability.EventPublish | SessionCapability.EventSubscribe
        | SessionCapability.CatalogPublish | SessionCapability.CatalogSubscribe;

    public static SessionCapability Legacy(bool dataOnly, bool incoming)
        => dataOnly ? DataSharing : incoming ? SessionCapability.InputReceive : SessionCapability.InputSend;

    public static bool Allows(SessionCapability granted, SessionCapability required)
        => required != SessionCapability.None && (granted & required) == required;

    public static SessionCapability Parse(IEnumerable<string>? names)
    {
        var result = SessionCapability.None;
        foreach (var name in names ?? [])
        {
            result |= name switch
            {
                "input.send" => SessionCapability.InputSend,
                "input.receive" => SessionCapability.InputReceive,
                "position.publish" => SessionCapability.PositionPublish,
                "position.subscribe" => SessionCapability.PositionSubscribe,
                "event.publish" => SessionCapability.EventPublish,
                "event.subscribe" => SessionCapability.EventSubscribe,
                "catalog.publish" => SessionCapability.CatalogPublish,
                "catalog.subscribe" => SessionCapability.CatalogSubscribe,
                "map.publish" => SessionCapability.MapPublish,
                "map.subscribe" => SessionCapability.MapSubscribe,
                _ => throw new ArgumentException("Unknown session capability: " + name)
            };
        }
        return result;
    }

    public static string[] ToWire(SessionCapability capabilities)
    {
        var result = new List<string>();
        foreach (var (flag, name) in new[]
        {
            (SessionCapability.InputSend, "input.send"), (SessionCapability.InputReceive, "input.receive"),
            (SessionCapability.PositionPublish, "position.publish"), (SessionCapability.PositionSubscribe, "position.subscribe"),
            (SessionCapability.EventPublish, "event.publish"), (SessionCapability.EventSubscribe, "event.subscribe"),
            (SessionCapability.CatalogPublish, "catalog.publish"), (SessionCapability.CatalogSubscribe, "catalog.subscribe"),
            (SessionCapability.MapPublish, "map.publish"), (SessionCapability.MapSubscribe, "map.subscribe")
        })
            if ((capabilities & flag) != 0) result.Add(name);
        return result.ToArray();
    }
}

