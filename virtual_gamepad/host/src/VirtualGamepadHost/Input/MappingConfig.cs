using System.Text.Json;
using VirtualGamepadHost.Model;

namespace VirtualGamepadHost.Input;

public sealed record Binding(string Source, string Target, double Value = 1.0, double Sensitivity = 1.0);

public sealed record MappingConfig(
    IReadOnlyList<Binding> Bindings,
    string StartPause = "F8",
    string EmergencyReset = "F9")
{
    public static MappingConfig Default => new(new[]
    {
        new Binding("keyboard:W", "axis:LeftY", 1.0),
        new Binding("keyboard:S", "axis:LeftY", -1.0),
        new Binding("keyboard:A", "axis:LeftX", -1.0),
        new Binding("keyboard:D", "axis:LeftX", 1.0),
        new Binding("keyboard:Space", "button:A"),
        new Binding("mouse:left", "trigger:Right"),
        new Binding("mouse:right", "trigger:Left"),
        new Binding("mouse:move_x", "axis:RightX", 1.0, 0.8),
        new Binding("mouse:move_y", "axis:RightY", 1.0, 0.8),
    });

    public static MappingConfig FromJson(JsonElement payload)
    {
        var startPause = payload.TryGetProperty("startPause", out var start) ? start.GetString() ?? "F8" : "F8";
        var emergencyReset = payload.TryGetProperty("emergencyReset", out var reset) ? reset.GetString() ?? "F9" : "F9";
        var bindings = new List<Binding>();

        if (payload.TryGetProperty("bindings", out var rawBindings) && rawBindings.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in rawBindings.EnumerateArray())
            {
                var source = item.GetProperty("source").GetString();
                var target = item.GetProperty("target").GetString();
                if (!string.IsNullOrWhiteSpace(source) && !string.IsNullOrWhiteSpace(target))
                {
                    bindings.AddRange(ExpandAlias(
                        source,
                        target,
                        item.TryGetProperty("value", out var value) ? value.GetDouble() : 1.0,
                        item.TryGetProperty("sensitivity", out var sensitivity) ? sensitivity.GetDouble() : 1.0));
                }
            }
        }
        else if (payload.TryGetProperty("bindings", out rawBindings) && rawBindings.ValueKind == JsonValueKind.Object)
        {
            foreach (var target in rawBindings.EnumerateObject())
            {
                foreach (var source in target.Value.EnumerateArray())
                {
                    var sourceName = source.GetString();
                    if (!string.IsNullOrWhiteSpace(sourceName))
                    {
                        bindings.AddRange(ExpandAlias(sourceName, target.Name, 1.0, 1.0));
                    }
                }
            }
        }

        return new MappingConfig(bindings, startPause, emergencyReset);
    }

    private static IEnumerable<Binding> ExpandAlias(string source, string target, double value, double sensitivity)
    {
        if (target.Contains(':'))
        {
            yield return new Binding(source, target, value, sensitivity);
            yield break;
        }

        if (Enum.TryParse<GamepadButton>(target, true, out _))
        {
            yield return new Binding(source, $"button:{target}", value, sensitivity);
            yield break;
        }

        if (target.Equals("LeftTrigger", StringComparison.OrdinalIgnoreCase))
        {
            yield return new Binding(source, "trigger:Left", value, sensitivity);
            yield break;
        }
        if (target.Equals("RightTrigger", StringComparison.OrdinalIgnoreCase))
        {
            yield return new Binding(source, "trigger:Right", value, sensitivity);
            yield break;
        }

        if (target.Equals("RightStick", StringComparison.OrdinalIgnoreCase))
        {
            if (source.EndsWith("move_x", StringComparison.OrdinalIgnoreCase))
            {
                yield return new Binding(source, "axis:RightX", value, sensitivity);
            }
            else if (source.EndsWith("move_y", StringComparison.OrdinalIgnoreCase))
            {
                yield return new Binding(source, "axis:RightY", value, sensitivity);
            }
            yield break;
        }

        if (target.Equals("LeftStick", StringComparison.OrdinalIgnoreCase))
        {
            var key = source.Contains(':') ? source[(source.IndexOf(':') + 1)..] : source;
            var axis = key.ToUpperInvariant() switch
            {
                "A" or "LEFT" => (GamepadAxis.LeftX, -1.0),
                "D" or "RIGHT" => (GamepadAxis.LeftX, 1.0),
                "W" or "UP" => (GamepadAxis.LeftY, 1.0),
                "S" or "DOWN" => (GamepadAxis.LeftY, -1.0),
                _ => ((GamepadAxis?)null, 0.0),
            };
            if (axis.Item1 is not null)
            {
                yield return new Binding(source, $"axis:{axis.Item1.Value}", axis.Item2 * value, sensitivity);
            }
        }
    }
}
