"""Protect desktop credentials with Windows DPAPI or the macOS login Keychain."""

from __future__ import annotations

import base64
import ctypes
import sys
import uuid
from ctypes import wintypes

PREFIX = "dpapi:v1:"
MACOS_PREFIX = "keychain:v1:"


def _transform(value: bytes, *, decrypt: bool) -> bytes:
    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(value)).from_buffer_copy(value)
    source = Blob(len(value), buffer)
    result = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    transform = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    transform.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    transform.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not transform(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise OSError("Windows could not protect or unlock this credential for the current user.")
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        kernel.LocalFree(result.data)


def protect(value: str) -> str:
    if not value or value.startswith((PREFIX, MACOS_PREFIX)):
        return value
    if sys.platform == "darwin":
        from diswhisper.macos_keychain import store

        account = str(uuid.uuid4())
        store(account, value)
        return MACOS_PREFIX + account
    if sys.platform != "win32":
        return value
    return PREFIX + base64.b64encode(_transform(value.encode("utf-8"), decrypt=False)).decode("ascii")


def unprotect(value: str) -> str:
    if value.startswith(MACOS_PREFIX):
        if sys.platform != "darwin":
            raise ValueError("This credential belongs to a Mac login Keychain. Enter it again on this computer.")
        from diswhisper.macos_keychain import read

        try:
            account = str(uuid.UUID(value[len(MACOS_PREFIX):]))
            return read(account)
        except (ValueError, OSError, UnicodeError):
            raise ValueError("This saved credential cannot be unlocked. Enter it again in the companion.") from None
    if not value.startswith(PREFIX):
        return value
    if sys.platform != "win32":
        raise ValueError("This credential belongs to a Windows user. Enter it again on this computer.")
    try:
        return _transform(base64.b64decode(value[len(PREFIX):], validate=True), decrypt=True).decode("utf-8")
    except (ValueError, OSError, UnicodeError):
        raise ValueError("This saved credential cannot be unlocked. Enter the token again in Connect Discord.") from None


def forget(value: str | None) -> None:
    """Remove superseded Keychain entries after a config write, or roll back a failed write."""
    if sys.platform == "darwin" and isinstance(value, str) and value.startswith(MACOS_PREFIX):
        from diswhisper.macos_keychain import delete

        try:
            delete(str(uuid.UUID(value[len(MACOS_PREFIX):])))
        except (ValueError, OSError):
            # Cleanup failure must not invalidate an already committed configuration.
            pass
