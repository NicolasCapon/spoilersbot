import os
import uuid
import cv2 as cv
import numpy as np
import scryfall
import requests
import random
import tqdm
import re
from io import BytesIO
from PIL import Image


def is_url(s: str):
    """Return True if string is valid url, False if not"""
    # django url validation regex (https://github.com/django/django/blob/stable/1.3.x/django/core/validators.py#L45)
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    return re.match(regex, s) is not None


def get_file_from_cv_image(image: np.ndarray):
    """
    transform image to binary file like object
    :param image: open_cv image array
    :return: None
    """
    # return cv.imencode('.jpg', image)[1].tostring()
    img = cv.cvtColor(image, cv.COLOR_BGR2RGB)
    im_pil = Image.fromarray(img)
    bio = BytesIO()
    bio.name = 'image.jpeg'
    im_pil.save(bio, 'JPEG')
    bio.seek(0)
    return bio


def get_illustration(card_image, box=(0.5, 0.332265, 0.855655, 0.448718)):
    """Take cv card image and return portion of image containing card illustration
    Typical card box (yolo):
        center_x = 0.502232
        center_y = 0.332265
        width_% = 0.855655
        height_% = 0.448718
    """
    height, width = card_image.shape[:2]
    x, y, w, h = box
    x1 = int(x*width - w*width / 2)
    x2 = int(x*width + w*width / 2)
    y1 = int(y*height - h*height / 2)
    y2 = int(y*height + h*height / 2)
    return card_image[y1:y2, x1:x2]


def descript_image(image):
    if isinstance(image, np.ndarray):
        cv_im = image
    elif is_url(image):
        cv_im = imread_url(image)
    else:
        cv_im = cv.imread(image, cv.IMREAD_UNCHANGED)

    cv_im = get_illustration(cv_im)
    hist = cv.calcHist([cv_im], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    hist = cv.normalize(hist, hist).flatten()
    return hist


def get_closest_match(ref, objects, limit=10):
    distances = sorted([(cv.compareHist(ref.descr, np.frombuffer(o, dtype=ref.descr.dtype), cv.HISTCMP_BHATTACHARYYA) * 100, np.frombuffer(o, dtype=ref.descr.dtype)) for o in objects], key=lambda x: x[0])[:limit]
    if len(distances):
        ref.conf = int(distances[0][0])
    return distances


def show(img, title='image opencv'):
    cv.imshow(title, img)
    if cv.waitKey() & 0xff == 27:
        quit()


def resize(image, width=None, height=None, inter=cv.INTER_AREA):
    """ Resize a photo while saving the ratio from https://www.pyimagesearch.com"""
    dim = None
    (h, w) = image.shape[:2]

    if width is None and height is None:
        return image

    if width is None:
        r = height / float(h)
        dim = (int(w * r), height)

    else:
        r = width / float(w)
        dim = (width, int(h * r))

    resized = cv.resize(image, dim, interpolation=inter)
    return resized


def overlay_image(im_background, img):
    (h, w) = im_background.shape[:2]
    im_background = resize(im_background, w*2, h*2)
    x_offset = y_offset = 50 # Modify
    # image should be a list of images
    im_background[y_offset:y_offset + img.shape[0], x_offset:x_offset + img.shape[1]] = img
    return im_background


def overlay_images(im_background, images):
    h, w = im_background.shape[:2]
    total_w = 0
    space = 1.5
    for image in images:
        i_h, i_w = image.shape[:2]
        total_w += int(i_w*space)

    im_background = cv.resize(im_background,
                              (total_w, int(max(i.shape[0] for i in images)*space)),
                              interpolation=cv.INTER_AREA)
    cpt = 0
    pos = []
    for n, image in enumerate(images):
        i_h, i_w = image.shape[:2]
        x_offset = cpt + random.randrange(int(i_w * (space - 1)))
        y_offset = random.randrange(int(i_h * (space - 1)))
        if image.shape[2] == 4:
            # For png image add transparency
            overlay_image_alpha(im_background,
                                image[:, :, 0:3],
                                (x_offset, y_offset),
                                image[:, :, 3] / 255.0)
        else:
            im_background[y_offset:y_offset + i_h, x_offset:x_offset + i_w] = image

        # compute position of image in background for yolo label
        center_x = round((x_offset + i_w / 2) / im_background.shape[1], 6)
        center_y = round((y_offset + i_h / 2) / im_background.shape[0], 6)
        width_ratio = round(i_w / im_background.shape[1], 6)
        heigh_ratio = round(i_h / im_background.shape[0], 6)
        pos.append((center_x, center_y, width_ratio, heigh_ratio))

        cpt += int(i_w*space)

    return resize(im_background, int(w*len(images)*0.75)), pos


def overlay_image_alpha(img, img_overlay, pos, alpha_mask):
    """Overlay img_overlay on top of img at the position specified by
    pos and blend using alpha_mask.

    Alpha mask must contain values within the range [0, 1] and be the
    same size as img_overlay.
    """

    x, y = pos

    # Image ranges
    y1, y2 = max(0, y), min(img.shape[0], y + img_overlay.shape[0])
    x1, x2 = max(0, x), min(img.shape[1], x + img_overlay.shape[1])

    # Overlay ranges
    y1o, y2o = max(0, -y), min(img_overlay.shape[0], img.shape[0] - y)
    x1o, x2o = max(0, -x), min(img_overlay.shape[1], img.shape[1] - x)

    # Exit if nothing to do
    if y1 >= y2 or x1 >= x2 or y1o >= y2o or x1o >= x2o:
        return

    channels = img.shape[2]

    alpha = alpha_mask[y1o:y2o, x1o:x2o]
    alpha_inv = 1.0 - alpha

    for c in range(channels):
        img[y1:y2, x1:x2, c] = (alpha * img_overlay[y1o:y2o, x1o:x2o, c] +
                                alpha_inv * img[y1:y2, x1:x2, c])


def imread_url(url, flags=cv.IMREAD_UNCHANGED):
    """Return cv image from URL, None if url invalid"""
    if not url:
        return
    resp = requests.get(url, stream=True, timeout=5)
    image = None
    if resp.ok:
        image = np.asarray(bytearray(resp.raw.read()), dtype="uint8")
        image = cv.imdecode(image, flags)
    return image


def generate_yolo_image(folder, cards):
    # cards = [scryfall.get_random_card() for i in range(im_num+1)]
    background = imread_url(scryfall.get_image_urls(cards.pop(), size="art_crop")[0])
    if background is not None:
        images = []
        for c in cards:
            im = imread_url(scryfall.get_image_urls(c, size="png")[0])
            if im is not None and im.shape[0]:
                images.append(im)
        image, positions = overlay_images(background, images)
        # Create unique filenames
        uid = uuid.uuid4().hex
        cv.imwrite(os.path.join(folder, f"{uid}.jpg"), image)
        write_yolo_label_image(os.path.join(folder, f"{uid}.txt"), 0, positions)


def write_yolo_label_image(filename, class_id, positions):
    text = "\n".join((f"{class_id} {format(x, '.6f')} {format(y, '.6f')} {format(w, '.6f')} {format(h, '.6f')}" for x, y, w, h in positions))
    with open(filename, "w") as file:
        file.write(text)


def create_archive(directory, filename):
    import tarfile
    with tarfile.open(os.path.join(directory, f"{filename}.tar.gz"), "w:gz") as tar:
        for file in tqdm.tqdm(os.listdir(directory)):
            filepath = os.path.join(directory, file)
            tar.add(filepath, arcname=os.path.basename(filepath))


if __name__ == "__main__":
    from yolo import Yolo
    import config
    yo = Yolo(config.model, config.classes, config.conf)
    subimages = yo.get_detected_objects("https://i.redd.it/aon35a1sebi61.png")
    print(len(subimages))

