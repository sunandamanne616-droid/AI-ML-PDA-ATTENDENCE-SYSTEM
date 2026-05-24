from pathlib import Path
import io
import zipfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from backend.auth import require_roles
from backend.models import User
from backend.excel_register import EXCEL_ROOT, get_subject_excel_path

router = APIRouter(prefix="/excel", tags=["Excel Downloads"])

@router.get("/subject/{semester}/{subject}")
def download_subject_excel(
    semester: int,
    subject: str,
    user: User = Depends(require_roles("admin", "faculty", "hod","principal")),
):
    path = get_subject_excel_path(semester, subject)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Excel not found for this subject+semester")

    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

@router.get("/semester/{semester}")
def download_semester_zip(
    semester: int,
    user: User = Depends(require_roles("admin", "hod")),
):
    sem_dir = EXCEL_ROOT / f"SEM_{semester}"
    if not sem_dir.exists():
        raise HTTPException(status_code=404, detail="No Excel files for this semester")

    files = list(sem_dir.glob("*.xlsx"))
    if not files:
        raise HTTPException(status_code=404, detail="No Excel files for this semester")

    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, arcname=f.name)

    mem.seek(0)
    zip_name = f"SEM_{semester}_EXCELS.zip"
    return StreamingResponse(
        mem,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
    )


