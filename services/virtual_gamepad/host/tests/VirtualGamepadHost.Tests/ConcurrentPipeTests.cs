using System.IO.Pipes;
using System.Text;
using VirtualGamepadHost.Driver;
using VirtualGamepadHost.Input;
using VirtualGamepadHost.Protocol;
using VirtualGamepadHost.Runtime;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Tests;

public sealed class ConcurrentPipeTests
{
    [Fact]
    public async Task UiAndAutomationClientsCanIssueRequestsWhileBothRemainConnected()
    {
        var store = new StateStore();
        var safety = new SafetyController(store);
        var router = new CommandRouter(store, safety, () => new HostStatus(safety.RunState, true, true, "test"));
        var pipeName = $"AutoModules.VirtualGamepad.Tests.{Guid.NewGuid():N}";
        var server = new NamedPipeServer(router, pipeName);
        using var cancellation = new CancellationTokenSource();
        var serverTask = server.RunAsync(cancellation.Token);

        await using var ui = await ConnectAsync(pipeName);
        await AssertHelloAsync(ui);

        await using var automation = await ConnectAsync(pipeName);
        await AssertHelloAsync(automation);

        // The first connection is not displaced when the second client joins.
        await AssertHelloAsync(ui);

        cancellation.Cancel();
        await serverTask.WaitAsync(TimeSpan.FromSeconds(2));
    }

    [Fact]
    public async Task CancellationCompletesWhileConnectedClientDoesNotReadALargeResponse()
    {
        var store = new StateStore();
        var safety = new SafetyController(store);
        var mapping = new MappingEngine(store, new MappingConfig(new[]
        {
            new Binding(new string('s', 512 * 1024), "button:A"),
        }));
        var router = new CommandRouter(
            store,
            safety,
            () => new HostStatus(safety.RunState, true, true, "test"),
            mapping);
        var pipeName = $"AutoModules.VirtualGamepad.Tests.{Guid.NewGuid():N}";
        var server = new NamedPipeServer(router, pipeName);
        using var cancellation = new CancellationTokenSource();
        var serverTask = server.RunAsync(cancellation.Token);

        await using var client = await ConnectAsync(pipeName);
        await SendGetConfigWithoutReadingAsync(client);

        // Give the server a chance to start writing the response.  The client
        // intentionally never reads it, so a native pipe write may be waiting
        // on its output buffer when shutdown starts.
        await Task.Delay(100);
        cancellation.Cancel();

        await serverTask.WaitAsync(TimeSpan.FromSeconds(2));
    }

    private static async Task<NamedPipeClientStream> ConnectAsync(string pipeName)
    {
        var client = new NamedPipeClientStream(
            ".",
            pipeName,
            PipeDirection.InOut,
            PipeOptions.Asynchronous);
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(2));
        await client.ConnectAsync(timeout.Token);
        return client;
    }

    private static async Task AssertHelloAsync(NamedPipeClientStream client)
    {
        using var reader = new StreamReader(client, Encoding.UTF8, leaveOpen: true);
        await using var writer = new StreamWriter(client, new UTF8Encoding(false), leaveOpen: true)
        {
            AutoFlush = true,
            NewLine = "\n",
        };
        await writer.WriteLineAsync("{\"id\":\"hello\",\"type\":\"hello\",\"payload\":{}}");
        var response = await reader.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(2));
        Assert.NotNull(response);
        Assert.Contains("\"ok\":true", response);
    }

    private static async Task SendGetConfigWithoutReadingAsync(NamedPipeClientStream client)
    {
        await using var writer = new StreamWriter(client, new UTF8Encoding(false), leaveOpen: true)
        {
            AutoFlush = true,
            NewLine = "\n",
        };
        await writer.WriteLineAsync("{\"id\":\"config\",\"type\":\"get_config\",\"payload\":{}}");
    }
}
