using VirtualGamepadHost.Model;
using VirtualGamepadHost.Runtime;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Tests;

public sealed class ReportLoopTests
{
    [Fact]
    public void SubmitOnceUsesNeutralWhenStoreIsPaused()
    {
        var store = new StateStore();
        var backend = new FakeXInputBackend();
        backend.Start();
        store.SetButton("test", GamepadButton.A, true);
        store.SetPaused(true);

        new ReportLoop(store, backend).SubmitOnce();

        Assert.Equal(GamepadState.Neutral, Assert.Single(backend.Reports));
    }
}
