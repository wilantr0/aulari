"""Tests for aulari.ui.mac_url_handler (LaunchServices is faked except in one macOS test)."""

import sys
import unittest
from unittest import mock

from aulari.ui import mac_url_handler

OTHER_APP = "com.example.moodle"


class AutomaticLoginTests(unittest.TestCase):
    """automatic_login_available(): only in the macOS bundle that opens moodlemobile://."""

    def available(self, platform: str, frozen: bool, handler: object) -> bool:
        """Return automatic_login_available() on a faked system and default app."""
        side_effect = handler if isinstance(handler, Exception) else None
        with (
            mock.patch("sys.platform", platform),
            mock.patch.object(sys, "frozen", frozen, create=True),
            mock.patch.object(
                mac_url_handler, "default_handler", return_value=handler, side_effect=side_effect
            ),
        ):
            result = mac_url_handler.automatic_login_available()
        return result

    def test_bundle_that_opens_the_scheme(self) -> None:
        """The app bundle is the default app (case does not matter): automatic login."""
        identifier = mac_url_handler.BUNDLE_IDENTIFIER.upper()
        self.assertTrue(self.available("darwin", True, identifier))

    def test_other_default_app_or_none(self) -> None:
        """Another app, or no app at all, opens the scheme: manual login."""
        self.assertFalse(self.available("darwin", True, OTHER_APP))
        self.assertFalse(self.available("darwin", True, None))

    def test_run_from_source(self) -> None:
        """Without the bundle (python -m aulari) there is no Info.plist: manual login."""
        self.assertFalse(self.available("darwin", False, mac_url_handler.BUNDLE_IDENTIFIER))

    def test_other_systems(self) -> None:
        """Windows has its own automatic login; other systems use the manual one."""
        self.assertFalse(self.available("win32", True, mac_url_handler.BUNDLE_IDENTIFIER))
        self.assertFalse(self.available("linux", True, mac_url_handler.BUNDLE_IDENTIFIER))

    def test_launchservices_error_means_manual(self) -> None:
        """If macOS cannot be asked, the login falls back to manual."""
        self.assertFalse(self.available("darwin", True, OSError("no framework")))


@unittest.skipUnless(sys.platform == "darwin", "LaunchServices is macOS only")
class DefaultHandlerTests(unittest.TestCase):
    """default_handler() against the real LaunchServices (read only)."""

    def test_unknown_scheme_has_no_app(self) -> None:
        """A scheme no app declares gives None."""
        self.assertIsNone(mac_url_handler.default_handler("aulari-test-no-such-scheme"))


if __name__ == "__main__":
    unittest.main()
