using System.Buffers.Binary;
using System.Security.Cryptography;

namespace LanInputSync;

/// <summary>Independent counters per delivery lane; retries carry the original ciphertext.</summary>
internal sealed class SecurePackets : IDisposable
{
    private readonly Guid _session;
    private readonly AesGcm _tx;
    private readonly AesGcm _rx;
    private readonly ulong[] _sent = new ulong[4];
    private readonly ulong[] _received = new ulong[4];
    public SecurePackets(Guid session, byte[] sendKey, byte[] receiveKey)
    {
        _session = session;
        _tx = new AesGcm(sendKey, 16);
        _rx = new AesGcm(receiveKey, 16);
    }
    public byte[] Encode(byte lane, ReadOnlySpan<byte> payload)
    {
        if (lane >= 4 || payload.Length > 512) throw new ArgumentOutOfRangeException(nameof(payload));
        var sequence = checked(++_sent[lane]);
        byte[] packet = new byte[26 + payload.Length + 16];
        packet[0] = 1;
        packet[1] = lane;
        _session.TryWriteBytes(packet.AsSpan(2, 16));
        BinaryPrimitives.WriteUInt64LittleEndian(packet.AsSpan(18), sequence);
        Span<byte> nonce = stackalloc byte[12];
        nonce.Clear(); nonce[0] = lane;
        BinaryPrimitives.WriteUInt64LittleEndian(nonce[4..], sequence);
        _tx.Encrypt(nonce, payload, packet.AsSpan(26, payload.Length), packet.AsSpan(26 + payload.Length, 16), packet.AsSpan(0, 26));
        return packet;
    }
    public bool TryDecode(ReadOnlySpan<byte> packet, out byte lane, out byte[] payload)
    {
        lane = 0; payload = [];
        if (packet.Length < 42 || packet.Length > 554 || packet[0] != 1 || packet[1] >= 4 || new Guid(packet.Slice(2, 16)) != _session) return false;
        lane = packet[1];
        ulong sequence = BinaryPrimitives.ReadUInt64LittleEndian(packet[18..]);
        if (sequence <= _received[lane]) return false;
        Span<byte> nonce = stackalloc byte[12];
        nonce.Clear(); nonce[0] = lane;
        BinaryPrimitives.WriteUInt64LittleEndian(nonce[4..], sequence);
        byte[] decoded = new byte[packet.Length - 42];
        try { _rx.Decrypt(nonce, packet.Slice(26, decoded.Length), packet[^16..], decoded, packet[..26]); }
        catch (CryptographicException) { return false; }
        _received[lane] = sequence;
        payload = decoded;
        return true;
    }
    public void Dispose() { _tx.Dispose(); _rx.Dispose(); }
}
