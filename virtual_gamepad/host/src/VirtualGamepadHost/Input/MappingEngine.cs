using VirtualGamepadHost.Model;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Input;

public sealed class MappingEngine
{
    private const int FullAxis = short.MaxValue;
    private readonly StateStore _store;
    private MappingConfig _config;
    private readonly HashSet<string> _activeSources = new(StringComparer.OrdinalIgnoreCase);

    public MappingEngine(StateStore store, MappingConfig? config = null)
    {
        _store = store;
        _config = config ?? MappingConfig.Default;
    }

    public MappingConfig Config => _config;

    public void SetConfig(MappingConfig config)
    {
        Validate(config);
        _config = config;
        _activeSources.Clear();
        _store.ClearSources("mapping:");
    }

    public void Apply(PhysicalInput input)
    {
        if (input.Type == PhysicalInputType.MouseMove)
        {
            ApplyMouseMove(input);
            return;
        }

        var active = input.Type is PhysicalInputType.KeyDown or PhysicalInputType.MouseButtonDown;
        if (active)
        {
            _activeSources.Add(input.Source);
        }
        else
        {
            _activeSources.Remove(input.Source);
        }

        foreach (var binding in _config.Bindings.Where(binding => binding.Source.Equals(input.Source, StringComparison.OrdinalIgnoreCase)))
        {
            ApplyBinding(binding, active);
        }
    }

    private void ApplyBinding(Binding binding, bool active)
    {
        var target = binding.Target.Split(':', 2);
        if (target.Length != 2)
        {
            return;
        }

        switch (target[0].ToLowerInvariant())
        {
            case "button" when Enum.TryParse<GamepadButton>(target[1], true, out var button):
                _store.SetButton(SourceId(binding), button, active);
                break;
            case "axis" when TryParseAxis(target[1], out var axis):
                _store.SetAxis(SourceId(binding), axis, active ? (int)(FullAxis * Math.Clamp(binding.Value, -1.0, 1.0)) : 0);
                break;
            case "trigger" when TryParseTrigger(target[1], out var trigger):
                _store.SetTrigger(SourceId(binding), trigger, active ? (int)(byte.MaxValue * Math.Clamp(binding.Value, 0.0, 1.0)) : 0);
                break;
        }
    }

    private void ApplyMouseMove(PhysicalInput input)
    {
        var horizontal = _config.Bindings.FirstOrDefault(binding => binding.Source.Equals("mouse:move_x", StringComparison.OrdinalIgnoreCase));
        var vertical = _config.Bindings.FirstOrDefault(binding => binding.Source.Equals("mouse:move_y", StringComparison.OrdinalIgnoreCase));
        if (horizontal is not null)
        {
            _store.SetAxis("mapping:mouse_x", GamepadAxis.RightX, (int)Math.Clamp(input.DeltaX * horizontal.Sensitivity * 1200, short.MinValue, short.MaxValue), TimeSpan.FromMilliseconds(40));
        }
        if (vertical is not null)
        {
            _store.SetAxis("mapping:mouse_y", GamepadAxis.RightY, (int)Math.Clamp(input.DeltaY * vertical.Sensitivity * 1200, short.MinValue, short.MaxValue), TimeSpan.FromMilliseconds(40));
        }
    }

    private static string SourceId(Binding binding) => $"mapping:{binding.Source}:{binding.Target}";

    private static void Validate(MappingConfig config)
    {
        if (config.Bindings.Any(binding => string.IsNullOrWhiteSpace(binding.Source) || string.IsNullOrWhiteSpace(binding.Target)))
        {
            throw new ArgumentException("Every binding requires a source and target.");
        }

        if (config.Bindings.Any(binding => double.IsNaN(binding.Value) || double.IsInfinity(binding.Value) || double.IsNaN(binding.Sensitivity) || double.IsInfinity(binding.Sensitivity)))
        {
            throw new ArgumentException("Binding values must be finite numbers.");
        }
    }

    private static bool TryParseAxis(string value, out GamepadAxis axis)
    {
        var normalized = value.Replace("_", string.Empty).ToLowerInvariant();
        return Enum.TryParse(normalized switch
        {
            "leftx" => nameof(GamepadAxis.LeftX),
            "lefty" => nameof(GamepadAxis.LeftY),
            "rightx" => nameof(GamepadAxis.RightX),
            "righty" => nameof(GamepadAxis.RightY),
            _ => string.Empty,
        }, true, out axis);
    }

    private static bool TryParseTrigger(string value, out GamepadTrigger trigger)
    {
        return Enum.TryParse(value, true, out trigger);
    }
}
