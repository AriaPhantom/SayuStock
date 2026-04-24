from PIL import ImageFont

def core_font(size):
    try:
        # Try to find a common font on the system
        return ImageFont.truetype("msyh.ttc", size)
    except:
        return ImageFont.load_default()
