from pathlib import Path

from django.core.exceptions import ValidationError


DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 3 * 1024 * 1024


def validate_uploaded_file(uploaded_file, *, allowed_extensions, max_size, label):
    if not uploaded_file:
        return
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValidationError(f"{label} must use one of these extensions: {allowed}.")
    if uploaded_file.size and uploaded_file.size > max_size:
        max_mb = max_size // (1024 * 1024)
        raise ValidationError(f"{label} must be {max_mb}MB or smaller.")


def validate_document_upload(uploaded_file):
    validate_uploaded_file(
        uploaded_file,
        allowed_extensions=DOCUMENT_EXTENSIONS,
        max_size=MAX_DOCUMENT_BYTES,
        label="Document upload",
    )


def validate_image_upload(uploaded_file):
    validate_uploaded_file(
        uploaded_file,
        allowed_extensions=IMAGE_EXTENSIONS,
        max_size=MAX_IMAGE_BYTES,
        label="Image upload",
    )
