import io
import numpy as np
from PIL import Image
import cv2

def load_image_bytes(image_input) -> Image.Image:
    """
    Accepts PIL.Image.Image or bytes/file-like object and returns an RGB PIL Image.
    """
    if isinstance(image_input, Image.Image):
        image = image_input
    elif isinstance(image_input, bytes):
        image = Image.open(io.BytesIO(image_input))
    elif hasattr(image_input, "read"):
        content = image_input.read()
        image = Image.open(io.BytesIO(content))
    else:
        raise ValueError("Unsupported image input type. Expected PIL Image, bytes, or file-like object.")

    if image.mode != "RGB":
        image = image.convert("RGB")
    return image


def calculate_blur_laplacian(pil_image: Image.Image) -> float:
    """
    Calculates the variance of Laplacian to estimate image sharpness/blur.
    Lower values indicate blurry images.
    """
    cv_img = np.array(pil_image)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_RGB2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def extract_red_hue_ratio(pil_image: Image.Image) -> float:
    """
    Extracts the ratio of pixels falling within the oral/pharyngeal red-hue range in HSV color space.
    """
    cv_img = np.array(pil_image)
    hsv = cv2.cvtColor(cv_img, cv2.COLOR_RGB2HSV)
    
    # Red hue wraps around 0/180 in HSV
    lower_red1 = np.array([0, 40, 40])
    upper_red1 = np.array([15, 255, 255])
    lower_red2 = np.array([160, 40, 40])
    upper_red2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    red_mask = cv2.bitwise_or(mask1, mask2)

    total_pixels = cv_img.shape[0] * cv_img.shape[1]
    red_pixels = np.count_nonzero(red_mask)
    return float(red_pixels / total_pixels) if total_pixels > 0 else 0.0


def extract_inflammation_intensity(pil_image: Image.Image) -> float:
    """
    Extracts mean intensity of red channel normalized by overall brightness.
    """
    cv_img = np.array(pil_image, dtype=np.float32)
    r = cv_img[:, :, 0]
    g = cv_img[:, :, 1]
    b = cv_img[:, :, 2]
    
    green_blue_avg = (g + b) / 2.0 + 1e-5
    red_ratio = r / green_blue_avg
    return float(np.mean(red_ratio))
