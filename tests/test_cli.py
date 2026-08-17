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
                "(base / (source.stem + '.md')).write_text('# Example\\n\\n## ABSTRACT\\nAccurate trajectory prediction supports safe autonomous driving.\\n\\n## Index Terms—trajectory prediction; autonomous driving\\n\\n## I. INTRODUCTION\\n\\n![](images/figure.png)\\n', encoding='utf-8')\n",
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
            self.assertEqual(record["abstract_excerpt"], "Accurate trajectory prediction supports safe autonomous driving.")
            self.assertEqual(record["tags"], ["trajectory-prediction", "autonomous-driving"])

    def test_ingest_rejects_an_empty_gpu_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            library = temp / "library"
            source = temp / "paper.pdf"
            source.write_bytes(b"%PDF-1.4\n% test fixture\n")
            command = [
                shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library),
                "ingest", str(source), "--label", "ExampleNet", "--gpu", "",
            ]
            result = subprocess.run(command, capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--gpu must be a non-empty CUDA device selection", result.stderr)
            self.assertEqual((library / "library.jsonl").read_text(encoding="utf-8"), "")

    def test_ingest_infers_year_and_label_from_underscore_filename(self):
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            library = temp / "library"
            source = temp / "2020_SPF2_Sequential_Pointcloud_Forecasting.pdf"
            source.write_bytes(b"%PDF-1.4\n% test fixture\n")
            command = [
                shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library),
                "ingest", str(source), "--label", source.stem, "--arxiv", "2003.08376", "--dry-run",
            ]
            result = subprocess.run(command, capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"paper_id": "2020-arXiv-SPF2-Sequential-Pointcloud-Forecasting"', result.stdout)
            self.assertIn('"year": 2020', result.stdout)

    def test_ingest_infers_year_from_arxiv_when_filename_has_no_year(self):
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            library = temp / "library"
            source = temp / "paper.pdf"
            source.write_bytes(b"%PDF-1.4\n% test fixture\n")
            command = [
                shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library),
                "ingest", str(source), "--label", "SPF2", "--arxiv", "2003.08376", "--dry-run",
            ]
            result = subprocess.run(command, capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"paper_id": "2020-arXiv-SPF2"', result.stdout)
            self.assertIn('"year": 2020', result.stdout)

    def test_ingest_infers_venue_and_model_label_from_filename(self):
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            library = temp / "library"
            source = temp / "2026_CVPR_SHARP.pdf"
            source.write_bytes(b"%PDF-1.4\n% test fixture\n")
            command = [
                shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library),
                "ingest", str(source), "--label", source.stem, "--dry-run",
            ]
            result = subprocess.run(command, capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"paper_id": "2026-CVPR-SHARP"', result.stdout)
            self.assertIn('"venue": "CVPR"', result.stdout)
            self.assertIn('"label": "SHARP"', result.stdout)

    def test_ingest_enriches_venue_and_model_from_converted_markdown(self):
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            library = temp / "library"
            source = temp / "paper.pdf"
            source.write_bytes(b"%PDF-1.4\n% test fixture\n")
            converter = temp / "converter.py"
            converter.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                "out = pathlib.Path(sys.argv[2]) / 'converted'\n"
                "out.mkdir(parents=True)\n"
                "(out / 'paper.md').write_text('# SHARP: Short-Window Streaming for Accurate Prediction\\n\\nThis CVPR paper is the Open Access version.\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )
            converter.chmod(0o755)
            command = [
                shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library),
                "ingest", str(source), "--year", "2026",
                "--converter", f"{shutil.which('python3') or 'python'} {converter} {{pdf}} {{output}}",
            ]
            result = subprocess.run(command, capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads((library / "library.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(record["paper_id"], "2026-CVPR-SHARP")
            self.assertEqual(record["venue"], "CVPR")
            self.assertEqual(record["label"], "SHARP")
            self.assertEqual(record["title"], "SHARP: Short-Window Streaming for Accurate Prediction")

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

    def test_link_code_matches_readme_and_verifies_repository_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            library = temp / "library"
            library.mkdir()
            record = {
                "schema_version": 1,
                "paper_id": "2025-CVPR-ExampleNet",
                "title": "ExampleNet: A Practical Model for Motion Prediction",
                "model_names": ["ExampleNet"],
            }
            (library / "library.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
            code_root = temp / "code"
            repository = code_root / "ExampleNet"
            repository.mkdir(parents=True)
            (repository / "README.md").write_text(
                "# ExampleNet: A Practical Model for Motion Prediction\n\n"
                "Official implementation.\n",
                encoding="utf-8",
            )
            for command in (
                ["git", "init"],
                ["git", "config", "user.email", "test@example.com"],
                ["git", "config", "user.name", "PaperMeld Test"],
                ["git", "add", "README.md"],
                ["git", "commit", "-m", "initial"],
                ["git", "remote", "add", "origin", "https://github.com/example/ExampleNet.git"],
            ):
                result = subprocess.run(command, cwd=repository, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            command = [
                shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library),
                "link-code", "--code-root", str(code_root),
            ]
            result = subprocess.run(command, capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(result.returncode, 0, result.stderr)
            linked = json.loads((library / "library.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(len(linked["code"]), 1)
            code = linked["code"][0]
            self.assertEqual(code["local_path"], str(repository.resolve()))
            self.assertEqual(code["repository_url"], "https://github.com/example/ExampleNet.git")
            self.assertIn("title", code["match_evidence"])
            self.assertEqual(len(code["commit"]), 40)
            verify = subprocess.run(
                [shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library), "verify"],
                capture_output=True,
                text=True,
                env=os.environ | {"PYTHONPATH": str(PROJECT / "src")},
            )
            self.assertEqual(verify.returncode, 0, verify.stderr)

    def test_link_code_ignores_a_model_mentioned_by_another_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            library = temp / "library"
            library.mkdir()
            record = {
                "schema_version": 1,
                "paper_id": "2025-CVPR-ExampleNet",
                "title": "ExampleNet: A Practical Model for Motion Prediction",
                "model_names": ["ExampleNet"],
            }
            (library / "library.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
            repository = temp / "code" / "Framework"
            repository.mkdir(parents=True)
            (repository / "README.md").write_text(
                "# Framework\n\nThis project uses ExampleNet as a baseline.\n",
                encoding="utf-8",
            )
            result = subprocess.run(["git", "init"], cwd=repository, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            command = [
                shutil.which("python3") or "python", "-m", "papermeld.cli", "--library", str(library),
                "link-code", "--code-root", str(repository.parent),
            ]
            result = subprocess.run(command, capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(PROJECT / "src")})
            self.assertEqual(result.returncode, 0, result.stderr)
            linked = json.loads((library / "library.jsonl").read_text(encoding="utf-8"))
            self.assertNotIn("code", linked)


if __name__ == "__main__":
    unittest.main()
