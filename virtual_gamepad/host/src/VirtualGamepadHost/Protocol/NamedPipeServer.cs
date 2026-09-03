using System.IO.Pipes;
using System.Text;

namespace VirtualGamepadHost.Protocol;

public sealed class NamedPipeServer
{
    public const string PipeName = "AutoModules.VirtualGamepad.v1";

    private readonly CommandRouter _router;

    public NamedPipeServer(CommandRouter router)
    {
        _router = router;
    }

    public async Task RunAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            await using var pipe = new NamedPipeServerStream(
                PipeName,
                PipeDirection.InOut,
                1,
                PipeTransmissionMode.Byte,
                PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly);

            await pipe.WaitForConnectionAsync(cancellationToken).ConfigureAwait(false);
            using var reader = new StreamReader(pipe, Encoding.UTF8, leaveOpen: true);
            await using var writer = new StreamWriter(pipe, new UTF8Encoding(false), leaveOpen: true)
            {
                AutoFlush = true,
                NewLine = "\n",
            };

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
}
