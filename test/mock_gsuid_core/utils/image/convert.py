import io
from PIL import Image

async def convert_img(img: Image.Image):
    if isinstance(img, Image.Image):
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    return img
