using Nefarius.ViGEm.Client;
using Nefarius.ViGEm.Client.Targets;
using Nefarius.ViGEm.Client.Targets.Xbox360;
using VirtualGamepadHost.Model;
using VirtualGamepadHost.Runtime;

namespace VirtualGamepadHost.Driver;

public sealed class ViGEmXInputBackend : IXInputBackend
{
    private ViGEmClient? _client;
    private readonly IXbox360Controller?[] _controllers = new IXbox360Controller?[2];
    private readonly IVirtualGamepad?[] _controllerBases = new IVirtualGamepad?[2];

    public bool IsConnected => _controllers.All(controller => controller is not null);

    public int ControllerCount => _controllers.Length;

    public void Start()
    {
        if (IsConnected)
        {
            return;
        }

        _client = new ViGEmClient();
        HostDiagnostics.Write("ViGEm backend starting");
        try
        {
            for (var index = 0; index < _controllers.Length; index++)
            {
                var target = _client.CreateXbox360Controller();
                var controllerBase = target as IVirtualGamepad
                    ?? throw new InvalidOperationException("The ViGEm client returned an unexpected controller type.");
                controllerBase.AutoSubmitReport = false;
                controllerBase.Connect();
                HostDiagnostics.Write($"ViGEm controller connected controller={index + 1}");
                _controllers[index] = target;
                _controllerBases[index] = controllerBase;
            }

            for (var index = 1; index <= ControllerCount; index++)
            {
                Submit(index, GamepadState.Neutral);
            }
        }
        catch
        {
            Stop();
            throw;
        }
    }

    public void Submit(int controllerNumber, GamepadState state)
    {
        if (controllerNumber is < 1 or > 2)
        {
            throw new ArgumentOutOfRangeException(nameof(controllerNumber), "Controller must be 1 or 2.");
        }

        var index = controllerNumber - 1;
        var controller = _controllers[index] ?? throw new InvalidOperationException("The virtual controller is not started.");
        var controllerBase = _controllerBases[index] ?? throw new InvalidOperationException("The virtual controller is not started.");
        controller.SetButtonsFull(state.Buttons);
        controller.SetSliderValue(Xbox360Slider.LeftTrigger, state.LeftTrigger);
        controller.SetSliderValue(Xbox360Slider.RightTrigger, state.RightTrigger);
        controller.SetAxisValue(Xbox360Axis.LeftThumbX, state.LeftStickX);
        controller.SetAxisValue(Xbox360Axis.LeftThumbY, state.LeftStickY);
        controller.SetAxisValue(Xbox360Axis.RightThumbX, state.RightStickX);
        controller.SetAxisValue(Xbox360Axis.RightThumbY, state.RightStickY);
        controllerBase.SubmitReport();
        if (state.Buttons != 0 || state.LeftStickX != 0 || state.LeftStickY != 0)
            HostDiagnostics.Write($"ViGEm SubmitReport controller={controllerNumber} buttons={state.Buttons} axes={state.LeftStickX},{state.LeftStickY}");
    }

    public void Stop()
    {
        if (_client is null && _controllers.All(controller => controller is null))
        {
            return;
        }

        try
        {
            for (var index = 1; index <= ControllerCount; index++)
            {
                Submit(index, GamepadState.Neutral);
            }
        }
        catch
        {
            // Shutdown must still disconnect even if the bus has disappeared.
        }

        foreach (var controllerBase in _controllerBases)
        {
            controllerBase?.Disconnect();
        }

        Array.Clear(_controllers);
        Array.Clear(_controllerBases);
        _client?.Dispose();
        _client = null;
    }

    public void Dispose() => Stop();
}
