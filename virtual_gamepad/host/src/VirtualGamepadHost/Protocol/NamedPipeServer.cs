using System.IO.Pipes;
using System.Text;

namespace VirtualGamepadHost.Protocol;

public sealed class NamedPipeServer
{
    public const string PipeName = "AutoModules.VirtualGamepad.v1";

    private readonly CommandRouter _router;
    private readonly string _pipeName;
    private readonly object _clientsGate = new();
    private readonly List<Task> _clientTasks = new();
    private readonly HashSet<NamedPipeServerStream> _clientPipes = new();
    private bool _stopping;

    public NamedPipeServer(CommandRouter router, string pipeName = PipeName)
    {
        _router = router;
        _pipeName = string.IsNullOrWhiteSpace(pipeName) ? throw new ArgumentException("Pipe name is required.", nameof(pipeName)) : pipeName;
    }

    public async Task RunAsync(CancellationToken cancellationToken)
    {
        using var cancellationRegistration = cancellationToken.Register(DisposeActiveClientPipes);
        while (!cancellationToken.IsCancellationRequested)
        {
            NamedPipeServerStream? pipe = null;
            try
            {
                pipe = new NamedPipeServerStream(
                    _pipeName,
                    PipeDirection.InOut,
                    NamedPipeServerStream.MaxAllowedServerInstances,
                    PipeTransmissionMode.Byte,
                    PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly);

                await pipe.WaitForConnectionAsync(cancellationToken).ConfigureAwait(false);
                StartClient(pipe, cancellationToken);
                pipe = null; // The detached client handler now owns the stream.
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                break;
            }
            catch (IOException ex)
            {
                Console.Error.WriteLine($"Pipe client disconnected: {ex.Message}");
            }
            catch (ObjectDisposedException) when (!cancellationToken.IsCancellationRequested)
            {
                // A client closed while a reader/writer was being disposed. Reopen the listener.
            }
            finally
            {
                pipe?.Dispose();
            }
        }

        Task[] clients;
        lock (_clientsGate)
        {
            clients = _clientTasks.ToArray();
        }
        try
        {
            await Task.WhenAll(clients).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            // Every connected client receives the same cancellation token.
            // Awaiting them first guarantees their streams have been disposed.
        }
    }

    private async Task ServeClientAsync(NamedPipeServerStream pipe, CancellationToken cancellationToken)
    {
        try
        {
            await using (pipe)
            using (var reader = new StreamReader(pipe, Encoding.UTF8, leaveOpen: true))
            await using (var writer = new StreamWriter(pipe, new UTF8Encoding(false), leaveOpen: true)
            {
                AutoFlush = true,
                NewLine = "\n",
            })
            {
                while (pipe.IsConnected && !cancellationToken.IsCancellationRequested)
                {
                    var line = await reader.ReadLineAsync(cancellationToken).ConfigureAwait(false);
                    if (line is null)
                    {
                        break;
                    }

                    string response;
                    try
                    {
                        response = _router.Handle(ProtocolSerializer.Parse(line));
                    }
                    catch (Exception ex)
                    {
                        response = ProtocolSerializer.Failure(null, "invalid_message", ex.Message);
                    }

                    await writer.WriteLineAsync(response).ConfigureAwait(false);
                }
            }
        }
        catch (IOException)
        {
            // A client may disconnect between a request and its response.
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            // Normal host shutdown: ReadLineAsync observes the shared token.
        }
        catch (ObjectDisposedException)
        {
            // Cancellation/disconnection may close the pipe before StreamWriter
            // flushes its final buffered bytes during async disposal.
        }
    }

    private void StartClient(NamedPipeServerStream pipe, CancellationToken cancellationToken)
    {
        Task? clientTask = null;
        lock (_clientsGate)
        {
            if (!_stopping)
            {
                _clientPipes.Add(pipe);
                clientTask = ServeClientAsync(pipe, cancellationToken);
                _clientTasks.Add(clientTask);
            }
        }

        if (clientTask is null)
        {
            // Cancellation won between accepting the connection and handing
            // it to a handler.  The handler must never be left untracked.
            pipe.Dispose();
            return;
        }

        _ = clientTask.ContinueWith(
            completed =>
            {
                lock (_clientsGate)
                {
                    _clientTasks.Remove(completed);
                    _clientPipes.Remove(pipe);
                }

                // The request loop handles expected disconnect/cancellation
                // errors.  Observe an unexpected fault so it never becomes an
                // unobserved task exception after the server has stopped.
                if (completed.IsFaulted)
                {
                    Console.Error.WriteLine($"Pipe client failed: {completed.Exception}");
                }
            },
            CancellationToken.None,
            TaskContinuationOptions.ExecuteSynchronously,
            TaskScheduler.Default);
    }

    private void DisposeActiveClientPipes()
    {
        NamedPipeServerStream[] pipes;
        lock (_clientsGate)
        {
            _stopping = true;
            pipes = _clientPipes.ToArray();
        }

        // Dispose outside the lock: disposal wakes a blocked Read/Write and
        // its completion continuation also needs the same gate.
        foreach (var pipe in pipes)
        {
            try
            {
                pipe.Dispose();
            }
            catch (ObjectDisposedException)
            {
                // Another disconnect/shutdown path already closed this pipe.
            }
        }
    }
}
