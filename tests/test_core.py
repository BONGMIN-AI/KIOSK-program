"""core 뼈대 테스트.  실행:  python -m unittest discover -s tests -v"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import audit, auth, schema, storage, validators

FAST = 1000  # 테스트에서는 PBKDF2 반복 횟수를 낮춰 빠르게


class PhoneTest(unittest.TestCase):
    def test_formats(self):
        for raw in ("01012345678", "010 1234 5678", "010-1234-5678", "+82 10-1234-5678"):
            self.assertEqual(validators.normalize_phone(raw), "010-1234-5678")

    def test_invalid(self):
        for raw in ("", "0111234567", "010-123-456", "abc"):
            with self.assertRaises(ValueError):
                validators.normalize_phone(raw)

    def test_mask(self):
        self.assertEqual(validators.mask_phone("010-1234-5678"), "010-****-5678")


class SchemaTest(unittest.TestCase):
    def test_next_id_and_validate(self):
        self.assertEqual(schema.next_id("C", {}), "C0001")
        self.assertEqual(schema.next_id("C", {"C0001": 1, "C0009": 2}), "C0010")
        rec = schema.new_record("C0001", "홍길동", "010-1234-5678", points=0)
        self.assertEqual(schema.validate_record(rec), [])
        del rec["name"]
        self.assertTrue(schema.validate_record(rec))


class VaultFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.ks = self.dir / "keystore.json"
        auth.init_keystore(self.ks, "admin", "pw1234", iterations=FAST)

    def tearDown(self):
        self.tmp.cleanup()

    def unlock(self, pw="pw1234", **kw):
        return auth.unlock(self.ks, self.dir, "admin", pw, **kw)

    def test_roundtrip_and_encrypted_on_disk(self):
        vault = self.unlock()
        vault.write("customers", {"C0001": {"name": "홍길동"}})
        self.assertEqual(vault.read("customers"), {"C0001": {"name": "홍길동"}})
        raw = (self.dir / "customers.json.enc").read_bytes()
        self.assertNotIn("홍길동".encode("utf-8"), raw)
        self.assertNotIn(b"customers", raw)

    def test_wrong_password_and_unknown_id(self):
        with self.assertRaises(auth.AuthFailed):
            self.unlock("wrong")
        with self.assertRaises(auth.AuthFailed):
            auth.unlock(self.ks, self.dir, "nobody", "pw1234")

    def test_lockout_and_recovery(self):
        clock = [1000.0]
        for _ in range(auth.MAX_FAILURES):
            with self.assertRaises(auth.AuthFailed):
                self.unlock("wrong", now=lambda: clock[0])
        with self.assertRaises(auth.LockedOut):
            self.unlock("pw1234", now=lambda: clock[0])  # 맞는 비밀번호도 잠금 중엔 거부
        clock[0] += auth.LOCK_SECONDS + 1
        self.assertIsNotNone(self.unlock("pw1234", now=lambda: clock[0]))

    def test_second_factor_must_pass(self):
        with self.assertRaises(auth.AuthFailed):
            self.unlock(second_factor=lambda: False)
        self.assertIsNotNone(self.unlock(second_factor=lambda: True))

    def test_second_admin_reads_same_data(self):
        v1 = self.unlock()
        v1.write("menu", {"M1": {"name": "아메리카노"}})
        auth.add_admin(self.ks, v1, "boss", "secret9", iterations=FAST)
        v2 = auth.unlock(self.ks, self.dir, "boss", "secret9")
        self.assertEqual(v2.read("menu")["M1"]["name"], "아메리카노")

    def test_admin_id_not_stored_in_plaintext(self):
        self.assertNotIn(b"admin", self.ks.read_bytes())

    def test_tamper_falls_back_to_backup(self):
        vault = self.unlock()
        vault.write("menu", {"v": 1})
        vault.write("menu", {"v": 2})  # 이때 v1 이 .bak 으로 남는다
        path = self.dir / "menu.json.enc"
        path.write_bytes(path.read_bytes()[:-5] + b"XXXXX")
        self.assertEqual(vault.read("menu"), {"v": 1})

    def test_both_corrupted_raises(self):
        vault = self.unlock()
        vault.write("menu", {"v": 1})
        (self.dir / "menu.json.enc").write_bytes(b"garbage")
        with self.assertRaises(storage.DataCorrupted):
            vault.read("menu")

    def test_bad_name_rejected(self):
        vault = self.unlock()
        with self.assertRaises(ValueError):
            vault.write("../evil", {})

    def test_wrong_key_cannot_read(self):
        vault = self.unlock()
        vault.write("menu", {"v": 1})
        other = storage.Vault(self.dir, __import__("core.crypto", fromlist=["x"]).new_data_key())
        with self.assertRaises(storage.DataCorrupted):
            other.read("menu")


class MemoryVaultTest(unittest.TestCase):
    def test_same_api(self):
        v = storage.MemoryVault()
        self.assertEqual(v.read("students", default={}), {})
        v.write("students", {"S1": {"name": "김"}})
        self.assertEqual(v.read("students"), {"S1": {"name": "김"}})
        self.assertEqual(v.list_names(), ["students"])


class AuditTest(unittest.TestCase):
    def test_chain_detects_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            log = audit.AuditLog(Path(d) / "audit.log")
            log.append("admin", "login")
            log.append("admin", "view", "C0001")
            log.append("admin", "edit", "C0001")
            self.assertEqual(log.verify(), (True, None))
            path = Path(d) / "audit.log"
            lines = path.read_text(encoding="utf-8").splitlines()
            entry = json.loads(lines[1])
            entry["target"] = "C9999"
            lines[1] = json.dumps(entry, ensure_ascii=False)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.assertEqual(log.verify(), (False, 2))


if __name__ == "__main__":
    unittest.main()
