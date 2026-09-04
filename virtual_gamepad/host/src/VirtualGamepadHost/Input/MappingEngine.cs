using VirtualGamepadHost.Model;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Input;

public sealed class MappingEngine
{
    private const int FullAxis = short.MaxValue;
    private readonly StateStore _store;
    private readonly object _configGate = new();
    private MappingConfig _config;

    public MappingEngine(StateStore store, MappingConfig? config = null)
    {
        _store = store;
        _config = config ?? MappingConfig.Default;
    }

    public MappingConfig Config
    {
        get
        {
            lock (_configGate)
            {
                return _config;
            }
        }
    }

    public void SetConfig(MappingConfig config)
    {
        Validate(config);
        lock (_configGate)
        {
            _config = config;
        }
        _store.ClearSources("mapping:");
    }

    public void Apply(PhysicalInput input)
    {
        var config = Config;
        if (input.Type == PhysicalInputType.MouseMove)
        {
            ApplyMouseMove(input, config);
            return;
        }

        var active = input.Type is PhysicalInputType.KeyDown or PhysicalInputType.MouseButtonDown;
        foreach (var binding in config.Bindings.Where(binding => binding.Source.Equals(input.Source, StringComparison.OrdinalIgnoreCase)))
        {
            ApplyBinding(binding, active);
        }
    }

    public bool ShouldSuppress(PhysicalInput input)
    {
        var config = Config;
        if (input.Type == PhysicalInputType.MouseMove)
        {
            if (config.MouseMovePassthrough)
            {
                return false;
            }

            return (input.DeltaX != 0 && config.Bindings.Any(binding => binding.Source.Equals("mouse:move_x", StringComparison.OrdinalIgnoreCase)))
                || (input.DeltaY != 0 && config.Bindings.Any(binding => binding.Source.Equals("mouse:move_y", StringComparison.OrdinalIgnoreCase)));
        }

        return config.Bindings.Any(binding => binding.Source.Equals(input.Source, StringComparison.OrdinalIgnoreCase));
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

    private void ApplyMouseMove(PhysicalInput input, MappingConfig config)
    {
        var horizontal = config.Bindings.FirstOrDefault(binding => binding.Source.Equals("mouse:move_x", StringComparison.OrdinalIgnoreCase));
        var vertical = config.Bindings.FirstOrDefault(binding => binding.Source.Equals("mouse:move_y", StringComparison.OrdinalIgnoreCase));
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

        if (double.IsNaN(config.MouseSensitivity) || double.IsInfinity(config.MouseSensitivity) || config.MouseSensitivity <= 0)
        {
            throw new ArgumentException("Mouse sensitivity must be a positive finite number.");
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
