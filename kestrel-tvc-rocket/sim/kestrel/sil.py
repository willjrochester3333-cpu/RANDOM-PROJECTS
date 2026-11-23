"""Software-in-the-loop bridge: flies the real C++ flight core (firmware/core) inside the simulator."""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys

import numpy as np

from .dynamics import FswOutput

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FW = os.path.join(ROOT, "firmware")
BUILD = os.path.join(FW, "build-host")
LIB = os.path.join(BUILD, "libkestrel_sil.dylib" if sys.platform == "darwin" else "libkestrel_sil.so")

STATE_NAMES = ["BOOT", "CALIBRATING", "READY", "BOOST", "COAST", "DESCENT", "LANDED", "ERROR"]


def build(force: bool = False) -> str:
    srcs = [os.path.join(FW, "core", "src", "flight.cpp"), os.path.join(FW, "sil", "kestrel_sil.cpp")]
    hdr_dir = os.path.join(FW, "core", "include", "kestrel")
    newest_src = max(os.path.getmtime(p) for p in srcs + [os.path.join(hdr_dir, h) for h in os.listdir(hdr_dir)])
    if force or not os.path.exists(LIB) or os.path.getmtime(LIB) < newest_src:
        os.makedirs(BUILD, exist_ok=True)
        subprocess.run(["cmake", "-S", FW, "-B", BUILD, "-DCMAKE_BUILD_TYPE=Release"], check=True,
                       stdout=subprocess.DEVNULL)
        subprocess.run(["cmake", "--build", BUILD, "-j4"], check=True, stdout=subprocess.DEVNULL)
    return LIB


_lib = None


def lib():
    global _lib
    if _lib is None:
        _lib = ctypes.CDLL(build())
        _lib.ksil_create.restype = ctypes.c_void_p
        _lib.ksil_create.argtypes = [ctypes.c_int]
        _lib.ksil_destroy.argtypes = [ctypes.c_void_p]
        _lib.ksil_set_param.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_float]
        _lib.ksil_set_param.restype = ctypes.c_int
        _lib.ksil_step.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.POINTER(ctypes.c_float),
                                   ctypes.POINTER(ctypes.c_float), ctypes.c_int, ctypes.c_float, ctypes.c_float,
                                   ctypes.POINTER(ctypes.c_float)]
        _lib.ksil_step.restype = ctypes.c_int
        _lib.ksil_motor_name.restype = ctypes.c_char_p
    return _lib


def motor_index(name: str) -> int:
    L = lib()
    for i in range(L.ksil_num_motors()):
        if L.ksil_motor_name(i).decode() == name:
            return i
    raise KeyError(f"motor {name} not in firmware motor_db.hpp (run firmware/tools/gen_motor_db.py)")


class SilFsw:
    """Adapter with the interface expected by dynamics.Simulation."""

    def __init__(self, params: dict | None = None, vbat: float = 7.8, boot_offset: float = 1.0):
        self.params = params or {}
        self.vbat = vbat
        self.boot_offset = boot_offset
        self.h = None
        self._g = (ctypes.c_float * 3)()
        self._a = (ctypes.c_float * 3)()
        self._o = (ctypes.c_float * 24)()
        self.trace = []

    def reset(self, sim):
        L = lib()
        if self.h:
            L.ksil_destroy(self.h)
        self.h = L.ksil_create(motor_index(sim.cfg.motor))
        for k, v in self.params.items():
            if L.ksil_set_param(self.h, k.encode(), float(v)) != 0:
                raise KeyError(f"unknown flight-core parameter {k}")
        self.t0 = -sim.cfg.t_pad - self.boot_offset   # FSW boots before the pad data starts

    def step(self, t, gyro, accel, baro_pa, baro_new, gps):
        L = lib()
        for i in range(3):
            self._g[i] = float(gyro[i])
            self._a[i] = float(accel[i])
        st = L.ksil_step(self.h, float(t - self.t0), self._g, self._a, 1 if baro_new else 0,
                         float(baro_pa) if baro_new else 0.0, self.vbat, self._o)
        o = self._o
        return FswOutput(gimbal_y_deg=o[0], gimbal_z_deg=o[1], tab_deg=(o[11], o[12], o[13], o[14]), deploy=o[2] > 0.5, state=st,
                         state_name=STATE_NAMES[st] if 0 <= st < len(STATE_NAMES) else "?",
                         extra=dict(alt_est=o[4], vz_est=o[5], tilt=o[6], deploy_reason=int(o[7]), abort=o[8] > 0.5,
                                    baro_alt=o[9], max_alt=o[10], roll_est=o[15], qbar_est=o[16], tab_share=o[17],
                                    fins_active=o[18] > 0.5))

    def __del__(self):
        try:
            if self.h and _lib is not None:
                _lib.ksil_destroy(self.h)
        except Exception:
            pass
