from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.helpers import ImmediateExecutor, build_pipeline_result
from web.progress import EVENT_文件完成
from web.server import app
from web.task_manager import BATCHES, _LOCK, get_batch


class WebBatchContractTests(unittest.TestCase):
    def setUp(self) -> None:
        unique = uuid.uuid4().hex[:8]
        self.upload_root = Path(f".tmp_test_uploads_{unique}")
        self.output_root = Path("output") / f"test_web_contract_{unique}"
        with _LOCK:
            BATCHES.clear()

    def tearDown(self) -> None:
        shutil.rmtree(self.upload_root, ignore_errors=True)
        shutil.rmtree(self.output_root, ignore_errors=True)
        with _LOCK:
            BATCHES.clear()

    def test_batch_status_event_and_report_share_same_review_fields(self) -> None:
        with (
            patch("web.api.UPLOAD_ROOT", self.upload_root),
            patch("web.api._EXECUTOR", ImmediateExecutor()),
            patch("web.runner.run_iterative_pipeline", side_effect=lambda config: build_pipeline_result(passed=False)),
        ):
            client = TestClient(app)
            create_resp = client.post(
                "/api/batches",
                files=[("files", ("sample.pdf", b"%PDF-1.4 test", "application/pdf"))],
            )
            self.assertEqual(create_resp.status_code, 200)
            batch_id = create_resp.json()["batch_id"]

            start_resp = client.post(
                f"/api/batches/{batch_id}/start",
                json={"output_root": self.output_root.as_posix()},
            )
            self.assertEqual(start_resp.status_code, 200)

            status_resp = client.get(f"/api/batches/{batch_id}")
            self.assertEqual(status_resp.status_code, 200)
            status_payload = status_resp.json()
            file_payload = status_payload["files"][0]

            for key in ("总分", "是否通过", "红线触发", "未通过原因", "评审轮次数"):
                self.assertIn(key, file_payload)
            for old_key in ("最终总评", "最终通过"):
                self.assertNotIn(old_key, file_payload)

            self.assertEqual(file_payload["总分"], 74.0)
            self.assertFalse(file_payload["是否通过"])
            self.assertTrue(file_payload["红线触发"])
            self.assertEqual(file_payload["未通过原因"], ["文本层不足需要OCR"])
            self.assertEqual(file_payload["评审轮次数"], 1)
            self.assertTrue(status_payload["report_ready"])

            batch = get_batch(batch_id)
            self.assertIsNotNone(batch)
            assert batch is not None

            complete_events = [event for event in batch.event_history if event.get("事件类型") == EVENT_文件完成]
            self.assertEqual(len(complete_events), 1)
            complete_event = complete_events[0]
            for key in ("总分", "是否通过", "红线触发", "未通过原因", "评审轮次数"):
                self.assertIn(key, complete_event)
            for old_key in ("最终总评", "最终通过"):
                self.assertNotIn(old_key, complete_event)

            report_path = batch.batch_report_path
            self.assertIsNotNone(report_path)
            assert report_path is not None
            report_payload = json.loads(report_path.read_text(encoding="utf-8"))
            file_entry = report_payload["文件列表"][0]
            for key in ("总分", "是否通过", "红线触发", "未通过原因", "评审轮次数"):
                self.assertIn(key, file_entry)
            for old_key in ("最终总评", "最终通过"):
                self.assertNotIn(old_key, file_entry)


if __name__ == "__main__":
    unittest.main()
