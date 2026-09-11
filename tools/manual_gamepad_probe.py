import time
from virtual_gamepad.client.python.virtual_gamepad_client import VirtualGamepadClient

client = VirtualGamepadClient()
client.connect()
print(client.status())
client.start(1)
client.set_state({'buttons': 12288}, source='manual-probe', ttl_ms=1000, controller=1)
print(client.state(1))
time.sleep(0.5)
client.set_state({'buttons': 0}, source='manual-probe', ttl_ms=200, controller=1)
client.close()
print('manual probe complete')
