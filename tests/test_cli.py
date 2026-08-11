import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class PaperMeldEndToEndTest(unittest.TestCase):
    def test_init_uses_portable_layout_for_a_new_library(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = Path(temporary) / "papers"
            command = [shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library), "init"]
            result = subprocess.run(command, capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ("inbox", "papers", "markdown", "assets", "library.jsonl"):
                self.assertTrue((library / name).exists(), name)

    def test_bootstrap_accepts_external_generic_markdown_without_rewriting_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            library = temp / "new-library"
            external = temp / "existing" / "notes"
            images = external / "figures"
            images.mkdir(parents=True)
            (images / "diagram.png").write_bytes(b"png")
            markdown = external / "Brown 2021 - Care Ethics.md"
            content = "# Care ethics in practice\n\n![](figures/diagram.png)\n"
            markdown.write_text(content, encoding="utf-8")
            command = [
                shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library),
                "bootstrap", "--markdown-dir", str(external),
            ]
            result = subprocess.run(command, capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(markdown.read_text(encoding="utf-8"), content)
            record = json.loads((library / "library.jsonl").read_text())
            self.assertEqual(record["paper_id"], "Brown 2021 - Care Ethics")
            self.assertEqual(record["markdown"], str(markdown.resolve()))
            self.assertEqual(record["image_mode"], "local")
            verify = subprocess.run([shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library), "verify"], capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(verify.returncode, 0, verify.stderr)
            preview = subprocess.run([shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library), "bootstrap", "--markdown-dir", str(external), "--dry-run"], capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(preview.returncode, 0, preview.stderr)

    def test_generic_converter_copies_an_external_pdf_by_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            library = temp / "library"
            source = temp / "downloaded.pdf"
            source.write_bytes(b"%PDF-1.4\n% test fixture\n")
            converter = temp / "converter.py"
            converter.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                "out = pathlib.Path(sys.argv[2]) / 'converted'\n"
                "(out / 'images').mkdir(parents=True)\n"
                "(out / 'images' / 'figure.png').write_bytes(b'png')\n"
                "(out / 'paper.md').write_text('# A general paper\\n\\n![](images/figure.png)\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )
            converter.chmod(0o755)
            command = [
                shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library), "ingest", str(source),
                "--converter", f"{shutil.which('python3') or 'python'} {converter} {{pdf}} {{output}}",
                "--year", "2024", "--venue", "Journal", "--title", "A general paper", "--label", "GeneralPaper",
            ]
            result = subprocess.run(command, capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(source.is_file(), "external input must not be moved by default")
            self.assertTrue((library / "papers" / "2024-Journal-GeneralPaper.pdf").is_file())
            output = library / "markdown" / "2024-Journal-GeneralPaper.md"
            self.assertIn("../assets/2024-Journal-GeneralPaper/images/figure.png", output.read_text())
            verify = subprocess.run([shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library), "verify"], capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(verify.returncode, 0, verify.stderr)

    def test_ingest_with_fake_mineru_rewrites_image_path_and_catalogs(self):
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            library = temp / "library"
            inbox = library / "INBOX"
            inbox.mkdir(parents=True)
            source = inbox / "Example.pdf"
            source.write_bytes(b"%PDF-1.4\n% test fixture\n")
            fake = temp / "fake_mineru.py"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                "source = pathlib.Path(sys.argv[sys.argv.index('-p') + 1])\n"
                "output = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])\n"
                "base = output / source.stem / 'hybrid_auto'\n"
                "(base / 'images').mkdir(parents=True)\n"
                "(base / 'images' / 'figure.png').write_bytes(b'png')\n"
                "(base / (source.stem + '.md')).write_text('# Example\\n\\n![](images/figure.png)\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            command = [
                shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library),
                "ingest", str(source), "--mineru", str(fake), "--year", "2025", "--venue", "CVPR", "--model", "ExampleNet",
            ]
            result = subprocess.run(command, capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(result.returncode, 0, result.stderr)
            markdown = library / "Markdown" / "ALL_MARKDOWN" / "2025-CVPR-ExampleNet.md"
            image = library / "Markdown" / "MINERU_OUTPUT" / "2025-CVPR-ExampleNet" / "hybrid_auto" / "images" / "figure.png"
            self.assertTrue(markdown.is_file())
            self.assertTrue(image.is_file())
            self.assertIn("../MINERU_OUTPUT/2025-CVPR-ExampleNet/hybrid_auto/images/figure.png", markdown.read_text())
            record = json.loads((library / "library.jsonl").read_text())
            self.assertEqual(record["paper_id"], "2025-CVPR-ExampleNet")

    def test_bootstrap_catalogs_existing_markdown_without_rewriting_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = Path(temporary) / "library"
            assets = library / "Markdown" / "MINERU_OUTPUT" / "source-paper" / "hybrid_auto" / "images"
            assets.mkdir(parents=True)
            (assets / "figure.png").write_bytes(b"png")
            markdown = library / "Markdown" / "ALL_MARKDOWN"
            markdown.mkdir(parents=True)
            source = markdown / "2025-CVPR-ExampleNet.md"
            content = "# ExampleNet\n\nAbstract: Trajectory prediction for autonomous driving.\n\nKeywords: trajectory prediction; autonomous driving\n\nIntroduction\n\n![](<../MINERU_OUTPUT/source-paper/hybrid_auto/images/figure.png>)\n"
            source.write_text(content, encoding="utf-8")
            command = [shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library), "bootstrap"]
            result = subprocess.run(command, capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads((library / "library.jsonl").read_text())
            self.assertEqual(record["paper_id"], "2025-CVPR-ExampleNet")
            self.assertEqual(record["image_mode"], "local")
            self.assertIn("trajectory-prediction", record["tags"])
            self.assertEqual(source.read_text(encoding="utf-8"), content)
            verify = subprocess.run([shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library), "verify"], capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(verify.returncode, 0, verify.stderr)

    def test_bootstrap_preserves_hyphenated_venue(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = Path(temporary) / "library"
            markdown = library / "Markdown" / "ALL_MARKDOWN"
            markdown.mkdir(parents=True)
            (markdown / "2025-RA-L-ExampleNet.md").write_text("# ExampleNet", encoding="utf-8")
            command = [shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library), "bootstrap"]
            result = subprocess.run(command, capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads((library / "library.jsonl").read_text())
            self.assertEqual(record["venue"], "RA-L")
            self.assertEqual(record["paper_id"], "2025-RA-L-ExampleNet")


if __name__ == "__main__":
    unittest.main()
