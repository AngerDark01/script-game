using VirtualGamepadHost.Model;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Tests;

public sealed class StateStoreTests
{
    [Fact]
    public void SourcesAreMergedAndCanBeClearedIndependently()
    {
        var store = new StateStore();
        store.SetButton("keyboard", GamepadButton.A, true);
        store.SetAxis("automation", GamepadAxis.LeftY, 20_000);

        Assert.True(store.Snapshot().IsPressed(GamepadButton.A));
        Assert.Equal((short)20_000, store.Snapshot().LeftStickY);

        store.ClearSource("keyboard");
        Assert.False(store.Snapshot().IsPressed(GamepadButton.A));
        Assert.Equal((short)20_000, store.Snapshot().LeftStickY);
    }

    [Fact]
    public void PauseAndClearAllReturnNeutralState()
    {
        var store = new StateStore();
        store.SetButton("test", GamepadButton.B, true);
        store.SetPaused(true);

        Assert.Equal(GamepadState.Neutral, store.Snapshot());
        store.SetPaused(false);
        store.ClearAll();
        Assert.Equal(GamepadState.Neutral, store.Snapshot());
    }

    [Fact]
    public async Task ExpiredSourceIsRemoved()
    {
        var store = new StateStore(TimeSpan.FromMilliseconds(15));
        store.SetButton("short", GamepadButton.X, true, TimeSpan.FromMilliseconds(15));

        await Task.Delay(40);

        Assert.False(store.Snapshot().IsPressed(GamepadButton.X));
    }
}
