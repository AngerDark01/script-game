using Nefarius.ViGEm.Client;
using Nefarius.ViGEm.Client.Targets;
using Nefarius.ViGEm.Client.Targets.Xbox360;
using VirtualGamepadHost.Model;

namespace VirtualGamepadHost.Driver;

public sealed class ViGEmXInputBackend : IXInputBackend
{
    private ViGEmClient? _client;
    private IXbox360Controller? _controller;
    private IVirtualGamepad? _controllerBase;

    public bool IsConnected => _controller is not null;

    public void Start()
    {
        if (_controller is not null)
        {
            return;
        }

        _client = new ViGEmClient();
        var target = _client.CreateXbox360Controller();
        _controller = target;
        _controllerBase = target as IVirtualGamepad
            ?? throw new InvalidOperationException("The ViGEm client returned an unexpected controller type.");
        _controllerBase.AutoSubmitReport = false;
        _controllerBase.Connect();
        Submit(GamepadState.Neutral);
    }

    public void Submit(GamepadState state)
    {
        var controller = _controller ?? throw new InvalidOperationException("The virtual controller is not started.");
        var controllerBase = _controllerBase ?? throw new InvalidOperationException("The virtual controller is not started.");
        controller.SetButtonsFull(state.Buttons);
        controller.SetSliderValue(Xbox360Slider.LeftTrigger, state.LeftTrigger);
        controller.SetSliderValue(Xbox360Slider.RightTrigger, state.RightTrigger);
        controller.SetAxisValue(Xbox360Axis.LeftThumbX, state.LeftStickX);
        controller.SetAxisValue(Xbox360Axis.LeftThumbY, state.LeftStickY);
        controller.SetAxisValue(Xbox360Axis.RightThumbX, state.RightStickX);
        controller.SetAxisValue(Xbox360Axis.RightThumbY, state.RightStickY);
        controllerBase.SubmitReport();
    }

    public void Stop()
    {
        if (_controller is null)
        {
            return;
        }

        try
        {
            Submit(GamepadState.Neutral);
        }
        catch
        {
            // Shutdown must still disconnect even if the bus has disappeared.
        }

        _controllerBase?.Disconnect();
        _controller = null;
        _controllerBase = null;
        _client?.Dispose();
        _client = null;
    }

    public void Dispose() => Stop();
}
