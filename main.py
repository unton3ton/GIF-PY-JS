import io
import re
import zipfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageSequence

app = FastAPI(title="GIF Processor")

MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_FILES_COUNT = 200

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.post("/api/split")
async def split_gif(file: UploadFile = File(...)):
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 20 MB)")
    try:
        img = Image.open(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")
    if img.format != 'GIF':
        raise HTTPException(status_code=400, detail="File is not a GIF")
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for i, frame in enumerate(ImageSequence.Iterator(img)):
            frame_buffer = io.BytesIO()
            frame.save(frame_buffer, format="PNG")
            zip_file.writestr(f"frame_{i:04d}.png", frame_buffer.getvalue())
    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.read(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=frames.zip"}
    )

def extract_number(filename: str) -> int:
    match = re.search(r'(\d+)', filename)
    return int(match.group(1)) if match else 0

@app.post("/api/assemble")
async def assemble_gif(files: list[UploadFile] = File(...), duration: int = Form(50)):
    if len(files) > MAX_FILES_COUNT:
        raise HTTPException(status_code=400, detail=f"Too many files (max {MAX_FILES_COUNT})")
    images = []
    for file in files:
        if file.size and file.size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File {file.filename} too large (max 20 MB)")
        contents = await file.read()
        try:
            img = Image.open(io.BytesIO(contents))
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid image: {file.filename}")
        images.append(img)
    if not images:
        raise HTTPException(status_code=400, detail="No images provided")
    images.sort(key=lambda img: extract_number(getattr(img, 'filename', '')))
    output_buffer = io.BytesIO()
    images[0].save(
        output_buffer,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        duration=duration,
        loop=0,
        optimize=True
    )
    output_buffer.seek(0)
    return Response(
        content=output_buffer.read(),
        media_type="image/gif",
        headers={"Content-Disposition": "attachment; filename=result.gif"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)