"""OCR cho trang PDF scan (không có lớp chữ): render trang bằng pypdfium2, nhận dạng bằng
Tesseract tiếng Việt.

Chỉ trang mà parser text không đọc được mới được OCR; trang có lớp chữ giữ nguyên text gốc.
Text OCR là bản máy đọc từ ảnh: trang được đánh dấu method="OCR" để quote/offset phía sau
biết bằng chứng đến từ OCR, không phải lớp chữ của tệp.

Engine được chọn bằng DOCUMENT_OCR:
- auto (mặc định): dùng Tesseract nếu máy có cả chương trình lẫn dữ liệu ngôn ngữ, không
  có thì bỏ qua (trang scan vẫn báo DOCUMENT_NOT_READABLE như trước).
- tesseract: bắt buộc; thiếu Tesseract/dữ liệu ngôn ngữ thì báo lỗi rõ ràng.
- off: không OCR.
"""

import io
import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

OCR_MODES = ("auto", "tesseract", "off")
DEFAULT_LANGUAGE = "vie"
DEFAULT_DPI = 300
DEFAULT_TIMEOUT_SECONDS = 120.0
# Chặn PDF scan quá dài làm treo run (mỗi trang ~1–3 giây ở 300 DPI).
DEFAULT_MAX_PAGES = 200


class OcrUnavailableError(RuntimeError):
    """OCR được yêu cầu nhưng máy thiếu Tesseract hoặc dữ liệu ngôn ngữ."""


class OcrFailedError(RuntimeError):
    """Tesseract chạy nhưng lỗi (timeout, tệp ảnh hỏng...)."""


class OcrEngine(Protocol):
    version: str

    def recognize(self, png: bytes) -> str: ...


def _candidates(command: str | None) -> list[str]:
    found = [command] if command else []
    if which := shutil.which("tesseract"):
        found.append(which)
    for base in (
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"),
    ):
        found.append(str(Path(base) / "Tesseract-OCR" / "tesseract.exe"))
    return found


class TesseractOcr:
    """Gọi chương trình `tesseract` qua stdin/stdout; không giữ ảnh hay text trên đĩa."""

    def __init__(
        self,
        command: str | None = None,
        *,
        language: str = DEFAULT_LANGUAGE,
        tessdata_dir: Path | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.language = language
        self.env = None
        if tessdata_dir is not None:
            self.env = {**os.environ, "TESSDATA_PREFIX": str(Path(tessdata_dir).resolve())}
        self.timeout_seconds = timeout_seconds
        self.command = next((c for c in _candidates(command) if c and Path(c).is_file()), None)
        if self.command is None:
            raise OcrUnavailableError(
                "Tesseract is not installed (set TESSERACT_CMD or add tesseract to PATH)"
            )
        languages = self._run(["--list-langs"]).split()
        if language not in languages:
            raise OcrUnavailableError(
                f"Tesseract has no '{language}' language data (install {language}.traineddata "
                "into its tessdata folder or set TESSDATA_PREFIX)"
            )
        first_line = self._run(["--version"]).splitlines()[0]
        self.version = f"tesseract-{first_line.split()[-1]}-{language}"

    def _run(self, args: list[str], data: bytes | None = None) -> str:
        try:
            completed = subprocess.run(
                [self.command, *args],
                input=data,
                capture_output=True,
                env=self.env,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise OcrFailedError("Tesseract timed out") from error
        if completed.returncode != 0:
            raise OcrFailedError(f"Tesseract exited with code {completed.returncode}")
        # --version/--list-langs có thể in ra stderr tùy bản build.
        return (completed.stdout or completed.stderr).decode("utf-8", errors="replace")

    def recognize(self, png: bytes) -> str:
        # psm 4: một cột chữ có cỡ khác nhau, hợp với văn bản hợp đồng; giữ khoảng trắng
        # đầu dòng để chunker nhận ra tiêu đề "Điều ..." như với lớp chữ.
        return self._run(
            [
                "stdin",
                "stdout",
                "-l",
                self.language,
                "--psm",
                "4",
                "-c",
                "preserve_interword_spaces=1",
            ],
            png,
        )


def build_ocr_engine(
    mode: str,
    *,
    command: str | None = None,
    language: str = DEFAULT_LANGUAGE,
    tessdata_dir: Path | None = None,
) -> OcrEngine | None:
    if mode not in OCR_MODES:
        raise ValueError(f"Unknown DOCUMENT_OCR={mode!r}; expected one of {OCR_MODES}")
    if mode == "off":
        return None
    try:
        import pypdfium2  # noqa: F401  (renders scanned pages; extra "ocr")
    except ImportError as error:
        if mode == "auto":
            return None
        raise OcrUnavailableError(
            "pypdfium2 is not installed (pip install backend[ocr])"
        ) from error
    try:
        return TesseractOcr(command, language=language, tessdata_dir=tessdata_dir)
    except OcrUnavailableError:
        if mode == "auto":
            return None
        raise


def render_pages(content: bytes, page_numbers: Sequence[int], dpi: int = DEFAULT_DPI):
    """PNG của các trang (đánh số từ 1) ở độ phân giải ``dpi``."""
    import pypdfium2

    pdf = pypdfium2.PdfDocument(content)
    try:
        for number in page_numbers:
            page = pdf[number - 1]
            try:
                image = page.render(scale=dpi / 72, grayscale=True).to_pil()
            finally:
                page.close()
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            yield number, buffer.getvalue()
    finally:
        pdf.close()
