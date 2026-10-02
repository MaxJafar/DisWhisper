"""Store desktop credentials in the login Keychain, without a shell or extra dependency."""

from __future__ import annotations

import ctypes
from contextlib import contextmanager

SERVICE = "org.diswhisper.credentials"


@contextmanager
def _query(account: str, value: str | None = None, *, read: bool = False):
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    security = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
    ptr = ctypes.c_void_p
    cf.CFStringCreateWithCString.argtypes = [ptr, ctypes.c_char_p, ctypes.c_uint32]
    cf.CFStringCreateWithCString.restype = ptr
    cf.CFDataCreate.argtypes = [ptr, ptr, ctypes.c_long]
    cf.CFDataCreate.restype = ptr
    cf.CFDictionaryCreateMutable.argtypes = [ptr, ctypes.c_long, ptr, ptr]
    cf.CFDictionaryCreateMutable.restype = ptr
    cf.CFDictionarySetValue.argtypes = [ptr, ptr, ptr]
    cf.CFRelease.argtypes = [ptr]
    cf.CFDataGetLength.argtypes = [ptr]
    cf.CFDataGetLength.restype = ctypes.c_long
    cf.CFDataGetBytePtr.argtypes = [ptr]
    cf.CFDataGetBytePtr.restype = ptr
    security.SecItemAdd.argtypes = [ptr, ptr]
    security.SecItemAdd.restype = ctypes.c_int32
    security.SecItemCopyMatching.argtypes = [ptr, ctypes.POINTER(ptr)]
    security.SecItemCopyMatching.restype = ctypes.c_int32
    security.SecItemDelete.argtypes = [ptr]
    security.SecItemDelete.restype = ctypes.c_int32

    def constant(name):
        return ptr.in_dll(security, name).value

    key_callbacks = ctypes.addressof(ctypes.c_byte.in_dll(cf, "kCFTypeDictionaryKeyCallBacks"))
    value_callbacks = ctypes.addressof(ctypes.c_byte.in_dll(cf, "kCFTypeDictionaryValueCallBacks"))
    query = cf.CFDictionaryCreateMutable(None, 0, key_callbacks, value_callbacks)
    owned = [query]
    try:
        cf.CFDictionarySetValue(query, constant("kSecClass"), constant("kSecClassGenericPassword"))
        for key, text in (("kSecAttrService", SERVICE), ("kSecAttrAccount", account)):
            string = cf.CFStringCreateWithCString(None, text.encode("utf-8"), 0x08000100)
            owned.append(string)
            cf.CFDictionarySetValue(query, constant(key), string)
        if value is not None:
            encoded = value.encode("utf-8")
            buffer = ctypes.create_string_buffer(encoded)
            data = cf.CFDataCreate(None, buffer, len(encoded))
            owned.append(data)
            cf.CFDictionarySetValue(query, constant("kSecValueData"), data)
        if read:
            cf.CFDictionarySetValue(query, constant("kSecReturnData"), ptr.in_dll(cf, "kCFBooleanTrue").value)
        yield security, cf, query
    finally:
        for item in reversed(owned):
            if item:
                cf.CFRelease(item)


def store(account: str, value: str) -> None:
    with _query(account, value) as (security, _cf, query):
        status = security.SecItemAdd(query, None)
    if status:
        raise ValueError(f"Your login Keychain could not save this credential (status {status}). Unlock it and try again.")


def read(account: str) -> str:
    with _query(account, read=True) as (security, cf, query):
        result = ctypes.c_void_p()
        status = security.SecItemCopyMatching(query, ctypes.byref(result))
        if status or not result.value:
            raise ValueError("This saved credential cannot be unlocked. Enter it again in the companion.")
        try:
            return ctypes.string_at(cf.CFDataGetBytePtr(result), cf.CFDataGetLength(result)).decode("utf-8")
        finally:
            cf.CFRelease(result)


def delete(account: str) -> None:
    with _query(account) as (security, _cf, query):
        status = security.SecItemDelete(query)
    if status not in (0, -25300):  # errSecItemNotFound is already deleted.
        raise ValueError(f"Keychain could not remove the replaced credential (status {status}).")
