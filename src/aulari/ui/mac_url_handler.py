"""Which app macOS opens moodlemobile:// links with (read only, LaunchServices).

The app bundle declares the scheme in its Info.plist (aulari.spec), so macOS
sends the login redirect straight to the running Aulari, where Tk calls
::tk::mac::LaunchURL (ui/main.py). Aulari never changes the default app for
the scheme: if another app (the official Moodle app, for example) is the
default, or when run from source without a bundle, the login falls back to
the manual steps.
"""

import ctypes
import ctypes.util
import logging
import sys

# Reverse-DNS id of the macOS app (aulari.spec imports it). macOS ties the
# app's Keychain access and settings to it, so it never changes (D8).
BUNDLE_IDENTIFIER = "io.github.alar89.aulari"
SCHEME = "moodlemobile"
CF_STRING_ENCODING_UTF8 = 0x08000100
BUFFER_BYTES = 512

logger = logging.getLogger(__name__)


def _load_framework(name: str) -> ctypes.CDLL:
    """Return a macOS framework loaded with ctypes.

    Raises: OSError if it cannot be found or loaded (for example, not on macOS).
    """
    path = ctypes.util.find_library(name)
    if path is None:
        raise OSError(f"Framework not found: {name}")
    result = ctypes.CDLL(path)
    return result


def _declare_functions(core_foundation: ctypes.CDLL, core_services: ctypes.CDLL) -> None:
    """Give ctypes the C signatures of the few functions used here."""
    core_foundation.CFStringCreateWithCString.restype = ctypes.c_void_p
    core_foundation.CFStringCreateWithCString.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_uint32,
    ]
    core_foundation.CFStringGetCString.restype = ctypes.c_bool
    core_foundation.CFStringGetCString.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_long,
        ctypes.c_uint32,
    ]
    core_foundation.CFRelease.restype = None
    core_foundation.CFRelease.argtypes = [ctypes.c_void_p]
    core_services.LSCopyDefaultHandlerForURLScheme.restype = ctypes.c_void_p
    core_services.LSCopyDefaultHandlerForURLScheme.argtypes = [ctypes.c_void_p]


def default_handler(scheme: str = SCHEME) -> str | None:
    """Return the bundle id of the app macOS opens scheme:// links with, or None.

    Raises: OSError if the macOS frameworks cannot be loaded.
    """
    result = None
    core_foundation = _load_framework("CoreFoundation")
    core_services = _load_framework("CoreServices")
    _declare_functions(core_foundation, core_services)
    name = core_foundation.CFStringCreateWithCString(
        None, scheme.encode("utf-8"), CF_STRING_ENCODING_UTF8
    )
    handler = core_services.LSCopyDefaultHandlerForURLScheme(name)
    if handler:
        buffer = ctypes.create_string_buffer(BUFFER_BYTES)
        if core_foundation.CFStringGetCString(
            handler, buffer, BUFFER_BYTES, CF_STRING_ENCODING_UTF8
        ):
            result = buffer.value.decode("utf-8")
        core_foundation.CFRelease(handler)
    core_foundation.CFRelease(name)
    return result


def activate_app() -> None:
    """Bring this app in front of the others, as a click on its Dock icon does.

    The browser hands the URL over without activating the app, so after
    'Open Aulari' the window would stay behind the browser.

    Raises: OSError if the Objective-C runtime cannot be loaded.
    """
    runtime = _load_framework("objc")
    runtime.objc_getClass.restype = ctypes.c_void_p
    runtime.objc_getClass.argtypes = [ctypes.c_char_p]
    runtime.sel_registerName.restype = ctypes.c_void_p
    runtime.sel_registerName.argtypes = [ctypes.c_char_p]
    address = ctypes.cast(runtime.objc_msgSend, ctypes.c_void_p).value
    # objc_msgSend is called with the exact C signature of each message.
    send_object = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(address)
    send_query = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(
        address
    )
    send_flag = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)(address)
    application = send_object(
        runtime.objc_getClass(b"NSApplication"), runtime.sel_registerName(b"sharedApplication")
    )
    ignoring_others = runtime.sel_registerName(b"activateIgnoringOtherApps:")
    responds = runtime.sel_registerName(b"respondsToSelector:")
    if send_query(application, responds, ignoring_others):
        send_flag(application, ignoring_others, True)
    else:
        send_object(application, runtime.sel_registerName(b"activate"))


def automatic_login_available() -> bool:
    """Return True inside the macOS app bundle when Aulari opens moodlemobile:// links."""
    result = False
    if sys.platform == "darwin" and getattr(sys, "frozen", False):
        handler = None
        try:
            handler = default_handler()
        except OSError as error:
            logger.warning("Could not ask macOS for the moodlemobile:// app: %s", error)
        result = handler is not None and handler.casefold() == BUNDLE_IDENTIFIER.casefold()
        if not result:
            logger.info("moodlemobile:// opens with %s: manual login", handler)
    return result
