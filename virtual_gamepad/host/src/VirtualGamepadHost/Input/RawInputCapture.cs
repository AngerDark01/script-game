using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace VirtualGamepadHost.Input;

public sealed class RawInputCapture : IDisposable
{
    private const int WM_INPUT = 0x00FF;
    private const int WM_HOTKEY = 0x0312;
    private const uint RID_INPUT = 0x10000003;
    private const uint RIDEV_INPUTSINK = 0x00000100;
    private const uint RIM_TYPEMOUSE = 0;
    private const uint RIM_TYPEKEYBOARD = 1;
    private const uint RI_KEY_BREAK = 1;
    private const uint RI_MOUSE_LEFT_BUTTON_DOWN = 0x0001;
    private const uint RI_MOUSE_LEFT_BUTTON_UP = 0x0002;
    private const uint RI_MOUSE_RIGHT_BUTTON_DOWN = 0x0004;
    private const uint RI_MOUSE_RIGHT_BUTTON_UP = 0x0008;
    private const uint RI_MOUSE_MIDDLE_BUTTON_DOWN = 0x0010;
    private const uint RI_MOUSE_MIDDLE_BUTTON_UP = 0x0020;
    private const uint RI_MOUSE_BUTTON_4_DOWN = 0x0040;
    private const uint RI_MOUSE_BUTTON_4_UP = 0x0080;
    private const uint RI_MOUSE_BUTTON_5_DOWN = 0x0100;
    private const uint RI_MOUSE_BUTTON_5_UP = 0x0200;

    private readonly Action<PhysicalInput> _onInput;
    private Thread? _thread;
    private uint _threadId;
    private RawInputWindow? _window;
    private readonly Action<HotkeyAction>? _onHotkey;

    public RawInputCapture(Action<PhysicalInput> onInput, Action<HotkeyAction>? onHotkey = null)
    {
        _onInput = onInput;
        _onHotkey = onHotkey;
    }

    public void Start()
    {
        if (_thread is not null)
        {
            return;
        }

        using var ready = new ManualResetEventSlim(false);
        Exception? startupError = null;
        _thread = new Thread(() =>
        {
            _threadId = GetCurrentThreadId();
            try
            {
                _window = new RawInputWindow(_onInput, _onHotkey);
                _window.CreateAndRegister();
                ready.Set();
                Application.Run();
            }
            catch (Exception ex)
            {
                startupError = ex;
                ready.Set();
            }
            finally
            {
                _window?.DestroyHandle();
                _window = null;
            }
        })
        {
            IsBackground = true,
            Name = "VirtualGamepad.RawInput",
        };
        _thread.SetApartmentState(ApartmentState.STA);
        _thread.Start();
        ready.Wait(TimeSpan.FromSeconds(3));
        if (startupError is not null)
        {
            throw new InvalidOperationException("Raw Input initialization failed.", startupError);
        }
    }

    public void Dispose()
    {
        if (_thread is null)
        {
            return;
        }

        if (_threadId != 0)
        {
            PostThreadMessage(_threadId, 0x0012, IntPtr.Zero, IntPtr.Zero);
        }
        if (!_thread.Join(TimeSpan.FromSeconds(2)))
        {
            _thread = null;
            return;
        }
        _thread = null;
    }

    private sealed class RawInputWindow : NativeWindow
    {
        private readonly Action<PhysicalInput> _onInput;
        private readonly Action<HotkeyAction>? _onHotkey;

        public RawInputWindow(Action<PhysicalInput> onInput, Action<HotkeyAction>? onHotkey)
        {
            _onInput = onInput;
            _onHotkey = onHotkey;
        }

        public void CreateAndRegister()
        {
            CreateHandle(new CreateParams
            {
                Caption = "AutoModules Virtual Gamepad Raw Input",
                ClassName = "STATIC",
                Style = 0,
            });

            var devices = new[]
            {
                new RawInputDevice { UsagePage = 0x01, Usage = 0x06, Flags = RIDEV_INPUTSINK, Target = Handle },
                new RawInputDevice { UsagePage = 0x01, Usage = 0x02, Flags = RIDEV_INPUTSINK, Target = Handle },
            };
            if (!RegisterRawInputDevices(devices, (uint)devices.Length, (uint)Marshal.SizeOf<RawInputDevice>()))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error());
            }

            if (_onHotkey is not null)
            {
                RegisterHotKey(Handle, 1, 0, (uint)Keys.F8);
                RegisterHotKey(Handle, 2, 0, (uint)Keys.F9);
            }
        }

        protected override void WndProc(ref Message m)
        {
            if (m.Msg == WM_INPUT)
            {
                ProcessInput(m.LParam);
            }
            else if (m.Msg == WM_HOTKEY && _onHotkey is not null)
            {
                _onHotkey(m.WParam.ToInt32() == 1 ? HotkeyAction.TogglePause : HotkeyAction.EmergencyReset);
            }
            base.WndProc(ref m);
        }

        private void ProcessInput(IntPtr handle)
        {
            uint size = 0;
            GetRawInputData(handle, RID_INPUT, null, ref size, (uint)Marshal.SizeOf<RawInputHeader>());
            if (size == 0 || size > 4096)
            {
                return;
            }

            var data = new byte[size];
            if (GetRawInputData(handle, RID_INPUT, data, ref size, (uint)Marshal.SizeOf<RawInputHeader>()) == uint.MaxValue)
            {
                return;
            }

            var type = BitConverter.ToUInt32(data, 0);
            var offset = IntPtr.Size == 8 ? 24 : 16;
            if (type == RIM_TYPEKEYBOARD && data.Length >= offset + 16)
            {
                var makeCode = BitConverter.ToUInt16(data, offset);
                var flags = BitConverter.ToUInt16(data, offset + 2);
                var virtualKey = BitConverter.ToUInt16(data, offset + 6);
                var source = $"keyboard:{KeyName(virtualKey, makeCode)}";
                _onInput(new PhysicalInput(source, (flags & RI_KEY_BREAK) == 0 ? PhysicalInputType.KeyDown : PhysicalInputType.KeyUp));
                return;
            }

            if (type == RIM_TYPEMOUSE && data.Length >= offset + 24)
            {
                var buttonFlags = BitConverter.ToUInt16(data, offset + 4);
                var deltaX = BitConverter.ToInt32(data, offset + 12);
                var deltaY = BitConverter.ToInt32(data, offset + 16);
                if (deltaX != 0 || deltaY != 0)
                {
                    _onInput(new PhysicalInput("mouse", PhysicalInputType.MouseMove, deltaX, deltaY));
                }
                EmitMouseButton(buttonFlags, RI_MOUSE_LEFT_BUTTON_DOWN, "left", true);
                EmitMouseButton(buttonFlags, RI_MOUSE_LEFT_BUTTON_UP, "left", false);
                EmitMouseButton(buttonFlags, RI_MOUSE_RIGHT_BUTTON_DOWN, "right", true);
                EmitMouseButton(buttonFlags, RI_MOUSE_RIGHT_BUTTON_UP, "right", false);
                EmitMouseButton(buttonFlags, RI_MOUSE_MIDDLE_BUTTON_DOWN, "middle", true);
                EmitMouseButton(buttonFlags, RI_MOUSE_MIDDLE_BUTTON_UP, "middle", false);
                EmitMouseButton(buttonFlags, RI_MOUSE_BUTTON_4_DOWN, "x1", true);
                EmitMouseButton(buttonFlags, RI_MOUSE_BUTTON_4_UP, "x1", false);
                EmitMouseButton(buttonFlags, RI_MOUSE_BUTTON_5_DOWN, "x2", true);
                EmitMouseButton(buttonFlags, RI_MOUSE_BUTTON_5_UP, "x2", false);
            }
        }

        private void EmitMouseButton(ushort flags, uint mask, string name, bool down)
        {
            if ((flags & mask) != 0)
            {
                _onInput(new PhysicalInput($"mouse:{name}", down ? PhysicalInputType.MouseButtonDown : PhysicalInputType.MouseButtonUp));
            }
        }
    }

    private static string KeyName(ushort virtualKey, ushort makeCode) => virtualKey switch
    {
        >= 0x30 and <= 0x39 => ((char)virtualKey).ToString(),
        >= 0x41 and <= 0x5A => ((char)virtualKey).ToString(),
        0x20 => "Space",
        0x0D => "Enter",
        0x1B => "Escape",
        0x10 => "Shift",
        0x11 => "Ctrl",
        0x12 => "Alt",
        0x09 => "Tab",
        0x08 => "Backspace",
        0x25 => "Left",
        0x26 => "Up",
        0x27 => "Right",
        0x28 => "Down",
        >= 0x70 and <= 0x7B => $"F{virtualKey - 0x6F}",
        _ => $"VK_{virtualKey:X2}_{makeCode:X2}",
    };

    [StructLayout(LayoutKind.Sequential)]
    private struct RawInputDevice
    {
        public ushort UsagePage;
        public ushort Usage;
        public uint Flags;
        public IntPtr Target;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct RawInputHeader
    {
        public uint Type;
        public uint Size;
        public IntPtr Device;
        public IntPtr WParam;
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool RegisterRawInputDevices([In] RawInputDevice[] devices, uint count, uint size);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint GetRawInputData(IntPtr rawInput, uint command, [Out] byte[]? data, ref uint size, uint headerSize);

    [DllImport("kernel32.dll")]
    private static extern uint GetCurrentThreadId();

    [DllImport("user32.dll")]
    private static extern bool PostThreadMessage(uint threadId, uint message, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool RegisterHotKey(IntPtr hWnd, int id, uint modifiers, uint virtualKey);
}

public enum HotkeyAction
{
    TogglePause,
    EmergencyReset,
}
