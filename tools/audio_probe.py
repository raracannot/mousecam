import ctypes, ctypes.wintypes as w
mm = ctypes.windll.winmm
n = mm.waveOutGetNumDevs()
print("waveOut devices:", n)
for i in range(n):
    caps = ctypes.create_string_buffer(64)
    if mm.waveOutGetDevCapsW(i, caps, 64) == 0:
        pass
