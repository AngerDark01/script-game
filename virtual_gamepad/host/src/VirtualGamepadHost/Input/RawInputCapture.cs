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
    private const int WH_KEYBOARD_LL = 13;
    private const int WH_MOUSE_LL = 14;
    private const int HC_ACTION = 0;
    private const int WM_KEYDOWN = 0x0100;
    private const int WM_KEYUP = 0x0101;
    private const int WM_SYSKEYDOWN = 0x0104;
    private const int WM_SYSKEYUP = 0x0105;
    private const int WM_MOUSEMOVE = 0x0200;
    private const int WM_LBUTTONDOWN = 0x0201;
    private const int WM_LBUTTONUP = 0x0202;
    private const int WM_RBUTTONDOWN = 0x0204;
    private const int WM_RBUTTONUP = 0x0205;
    private const int WM_MBUTTONDOWN = 0x0207;
    private const int WM_MBUTTONUP = 0x0208;
    private const int WM_XBUTTONDOWN = 0x020B;
    private const int WM_XBUTTONUP = 0x020C;

    private readonly Action<PhysicalInput> _onInput;
    private readonly Func<PhysicalInput, bool>? _shouldSuppress;
    private Thread? _thread;
    private uint _threadId;
    private RawInputWindow? _window;
    private readonly Action<HotkeyAction>? _onHotkey;

    public string CaptureMode => _window?.CaptureMode ?? "starting";

    public RawInputCapture(
        Action<PhysicalInput> onInput,
        Action<HotkeyAction>? onHotkey = null,
        Func<PhysicalInput, bool>? shouldSuppress = null)
    {
        _onInput = onInput;
        _onHotkey = onHotkey;
        _shouldSuppress = shouldSuppress;
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
                _window = new RawInputWindow(_onInput, _onHotkey, _shouldSuppress);
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
                _window?.DisposeResources();
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
        private readonly Func<PhysicalInput, bool>? _shouldSuppress;
        private readonly LowLevelHookProc _keyboardHookProc;
        private readonly LowLevelHookProc _mouseHookProc;
        private IntPtr _keyboardHook;
        private IntPtr _mouseHook;
        private bool _hasMousePoint;
        private int _lastMouseX;
        private int _lastMouseY;

        public string CaptureMode { get; private set; } = "starting";

        public RawInputWindow(
            Action<PhysicalInput> onInput,
            Action<HotkeyAction>? onHotkey,
            Func<PhysicalInput, bool>? shouldSuppress)
        {
            _onInput = onInput;
            _onHotkey = onHotkey;
            _shouldSuppress = shouldSuppress;
            _keyboardHookProc = KeyboardHookProc;
            _mouseHookProc = MouseHookProc;
        }

        public void CreateAndRegister()
        {
            CreateHandle(new CreateParams
            {
                Caption = "AutoModules Virtual Gamepad Raw Input",
                ClassName = "STATIC",
                Style = 0,
            });

            if (_onHotkey is not null)
            {
                RegisterHotKey(Handle, 1, 0, (uint)Keys.F7);
                RegisterHotKey(Handle, 2, 0, (uint)Keys.F8);
                RegisterHotKey(Handle, 3, 0, (uint)Keys.F9);
            }

            if (!TryInstallLowLevelHooks())
            {
                RegisterRawInputFallback();
                CaptureMode = "Raw Input fallback (physical input cannot be suppressed)";
            }
            else
            {
                CaptureMode = "Global keyboard/mouse interception enabled";
            }
        }

        public void DisposeResources()
        {
            if (_keyboardHook != IntPtr.Zero)
            {
                UnhookWindowsHookEx(_keyboardHook);
                _keyboardHook = IntPtr.Zero;
            }
            if (_mouseHook != IntPtr.Zero)
            {
                UnhookWindowsHookEx(_mouseHook);
                _mouseHook = IntPtr.Zero;
            }
        }

        private bool TryInstallLowLevelHooks()
        {
            var module = GetModuleHandle(null);
            _keyboardHook = SetWindowsHookEx(WH_KEYBOARD_LL, _keyboardHookProc, module, 0);
            _mouseHook = SetWindowsHookEx(WH_MOUSE_LL, _mouseHookProc, module, 0);
            if (_keyboardHook != IntPtr.Zero && _mouseHook != IntPtr.Zero)
            {
                return true;
            }

            DisposeResources();
            return false;
        }

        private void RegisterRawInputFallback()
        {
            var devices = new[]
            {
                new RawInputDevice { UsagePage = 0x01, Usage = 0x06, Flags = RIDEV_INPUTSINK, Target = Handle },
                new RawInputDevice { UsagePage = 0x01, Usage = 0x02, Flags = RIDEV_INPUTSINK, Target = Handle },
            };
            if (!RegisterRawInputDevices(devices, (uint)devices.Length, (uint)Marshal.SizeOf<RawInputDevice>()))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error());
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
                _onHotkey(m.WParam.ToInt32() switch
                {
                    1 => HotkeyAction.ToggleController1,
                    2 => HotkeyAction.ToggleController2,
                    _ => HotkeyAction.EmergencyResetAll,
                });
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

        private IntPtr KeyboardHookProc(int code, IntPtr wParam, IntPtr lParam)
        {
            if (code >= HC_ACTION)
            {
                var message = wParam.ToInt32();
                if (message is WM_KEYDOWN or WM_SYSKEYDOWN or WM_KEYUP or WM_SYSKEYUP)
                {
                    var data = Marshal.PtrToStructure<KbdLlHookStruct>(lParam);
                    var input = new PhysicalInput(
                        $"keyboard:{KeyName((ushort)data.VirtualKey, (ushort)data.ScanCode)}",
                        message is WM_KEYDOWN or WM_SYSKEYDOWN ? PhysicalInputType.KeyDown : PhysicalInputType.KeyUp);
                    if (HandleHookInput(input))
                    {
                        return (IntPtr)1;
                    }
                }
            }

            return CallNextHookEx(_keyboardHook, code, wParam, lParam);
        }

        private IntPtr MouseHookProc(int code, IntPtr wParam, IntPtr lParam)
        {
            if (code >= HC_ACTION)
            {
                var message = wParam.ToInt32();
                var data = Marshal.PtrToStructure<MsLlHookStruct>(lParam);
                if (message == WM_MOUSEMOVE)
                {
                    var deltaX = _hasMousePoint ? data.Point.X - _lastMouseX : 0;
                    var deltaY = _hasMousePoint ? data.Point.Y - _lastMouseY : 0;
                    _lastMouseX = data.Point.X;
                    _lastMouseY = data.Point.Y;
                    _hasMousePoint = true;
                    if (deltaX != 0 || deltaY != 0)
                    {
                        var input = new PhysicalInput("mouse", PhysicalInputType.MouseMove, deltaX, deltaY);
                        if (HandleHookInput(input))
                        {
                            return (IntPtr)1;
                        }
                    }
                }
                else if (TryMouseButton(message, data.MouseData, out var input))
                {
                    if (HandleHookInput(input))
                    {
                        return (IntPtr)1;
                    }
                }
            }

            return CallNextHookEx(_mouseHook, code, wParam, lParam);
        }

        private bool HandleHookInput(PhysicalInput input)
        {
            try
            {
                _onInput(input);
                return _shouldSuppress?.Invoke(input) == true;
            }
            catch
            {
                return false;
            }
        }

        private static bool TryMouseButton(int message, uint mouseData, out PhysicalInput input)
        {
            var down = message is WM_LBUTTONDOWN or WM_RBUTTONDOWN or WM_MBUTTONDOWN or WM_XBUTTONDOWN;
            var up = message is WM_LBUTTONUP or WM_RBUTTONUP or WM_MBUTTONUP or WM_XBUTTONUP;
            var name = message switch
            {
                WM_LBUTTONDOWN or WM_LBUTTONUP => "left",
                WM_RBUTTONDOWN or WM_RBUTTONUP => "right",
                WM_MBUTTONDOWN or WM_MBUTTONUP => "middle",
                WM_XBUTTONDOWN or WM_XBUTTONUP => (mouseData >> 16) switch
                {
                    1 => "x1",
                    2 => "x2",
                    _ => string.Empty,
                },
                _ => string.Empty,
            };
            if (!down && !up || string.IsNullOrEmpty(name))
            {
                input = default!;
                return false;
            }

            input = new PhysicalInput($"mouse:{name}", down ? PhysicalInputType.MouseButtonDown : PhysicalInputType.MouseButtonUp);
            return true;
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

    private delegate IntPtr LowLevelHookProc(int code, IntPtr wParam, IntPtr lParam);

    [StructLayout(LayoutKind.Sequential)]
    private struct KbdLlHookStruct
    {
        public uint VirtualKey;
        public uint ScanCode;
        public uint Flags;
        public uint Time;
        public IntPtr ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MsLlHookStruct
    {
        public Point Point;
        public uint MouseData;
        public uint Flags;
        public uint Time;
        public IntPtr ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Point
    {
        public int X;
        public int Y;
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr SetWindowsHookEx(int hookType, LowLevelHookProc callback, IntPtr module, uint threadId);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool UnhookWindowsHookEx(IntPtr hook);

    [DllImport("user32.dll")]
    private static extern IntPtr CallNextHookEx(IntPtr hook, int code, IntPtr wParam, IntPtr lParam);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr GetModuleHandle(string? moduleName);
}

public enum HotkeyAction
{
    ToggleController1,
    ToggleController2,
    EmergencyResetAll,
}
