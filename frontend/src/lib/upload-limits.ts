export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
export const MAX_DOCUMENT_PAGES = 3;
export const UPLOAD_LIMIT_LABEL = "Up to 5 MB and 3 pages";

export function getUploadSizeError(file: Blob): string | null {
  return !file.size || file.size > MAX_UPLOAD_BYTES
    ? "Choose a non-empty file up to 5 MB. Documents are limited to 3 pages."
    : null;
}
