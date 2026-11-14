import subprocess
import unittest
from pathlib import Path
from scripts.mcp_cdp_bridge import parse_devtools_sockets

REPO_ROOT = Path(__file__).resolve().parent.parent

SAMPLE_PROC_NET_UNIX = """Num       RefCount Protocol Flags    Type St Inode Path
00000000: 00000002 00000000 00010000 0001 01 12345 @chrome_devtools_remote
00000000: 00000002 00000000 00010000 0001 01 12346 @kiwi_devtools_remote_999
00000000: 00000002 00000000 00010000 0001 01 12347 /dev/socket/zygote
"""


class TestMcpCdpBridge(unittest.TestCase):
    def test_parse_devtools_sockets(self):
        sockets = parse_devtools_sockets(SAMPLE_PROC_NET_UNIX)
        self.assertEqual(sockets, ["chrome_devtools_remote", "kiwi_devtools_remote_999"])

    def test_deploy_shizuku_requires_apk_arg(self):
        res = subprocess.run(
            ["bash", str(REPO_ROOT / "scripts/deploy_shizuku.sh")],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Usage:", res.stderr + res.stdout)


    def test_help_includes_local_chromium_flag(self):
        res = subprocess.run(
            ["python3", str(REPO_ROOT / "scripts/mcp_cdp_bridge.py"), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--local-chromium", res.stdout)


if __name__ == "__main__":
    unittest.main()
