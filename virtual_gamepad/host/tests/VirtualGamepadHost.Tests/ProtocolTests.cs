using System.Text.Json;
using VirtualGamepadHost.Driver;
using VirtualGamepadHost.Model;
using VirtualGamepadHost.Protocol;
using VirtualGamepadHost.Runtime;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Tests;

public sealed class ProtocolTests
{
    [Fact]
    public void RouterAcceptsButtonAndAxisCommands()
    {
        var store = new StateStore();
        var safety = new SafetyController(store);
        var router = new CommandRouter(
            store,
            safety,
            () => new HostStatus(safety.RunState, true, true, "test"));

        var button = ProtocolSerializer.Parse("{\"id\":\"1\",\"type\":\"button\",\"payload\":{\"source\":\"test\",\"button\":\"A\",\"action\":\"press\"}}");
        var axis = ProtocolSerializer.Parse("{\"id\":\"2\",\"type\":\"set_axis\",\"payload\":{\"source\":\"test\",\"axis\":\"left_y\",\"value\":32767}}");

        Assert.Contains("\"ok\":true", router.Handle(button));
        Assert.Contains("\"ok\":true", router.Handle(axis));
        Assert.True(store.Snapshot().IsPressed(GamepadButton.A));
        Assert.Equal((short)32767, store.Snapshot().LeftStickY);
    }

    [Fact]
    public void RouterRejectsUnknownTypesAndInvalidAxes()
    {
        var store = new StateStore();
        var safety = new SafetyController(store);
        var router = new CommandRouter(store, safety, () => new HostStatus(safety.RunState, true, true, "test"));

        var unknown = ProtocolSerializer.Parse("{\"id\":\"x\",\"type\":\"nope\",\"payload\":{}}");
        var invalid = ProtocolSerializer.Parse("{\"id\":\"y\",\"type\":\"set_axis\",\"payload\":{\"source\":\"test\",\"axis\":\"bad\",\"value\":0}}");

        Assert.Contains("unknown_type", router.Handle(unknown));
        Assert.Contains("invalid_argument", router.Handle(invalid));
    }

    [Fact]
    public void StartIsRejectedWhenTheVirtualDeviceIsUnavailable()
    {
        var store = new StateStore();
        var safety = new SafetyController(store);
        var router = new CommandRouter(store, safety, () => new HostStatus(safety.RunState, false, false, "missing"), deviceReady: () => false);
        var start = ProtocolSerializer.Parse("{\"id\":\"1\",\"type\":\"start\",\"payload\":{}}");

        Assert.Contains("device_unavailable", router.Handle(start));
        Assert.Equal(RunState.Ready, safety.RunState);
    }
}
