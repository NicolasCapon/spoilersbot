import re
import logging
import im_utils
import cv2
import config
from yolo import Yolo
from model import Image


class SpoilerDetector:
    """
    Class to handle spoilers
    """

    distance_conf = 30
    reddit_set_reg = r"^\[(.{3,4})\]"

    def is_reddit_spoiler(self, submission):
        """
        Test if a reddit submission can be considered as a spoiler
        :param submission: PRAW submission object
        :return: True if submission is spoiler, False if not
        """
        # Discard any submission containing no external link to a potential spoiler
        if submission.domain == "self.magicTCG":
            return False
        # If submission is flaired or tag as spoiler:
        elif submission.spoiler or submission.link_flair_text == "Spoiler":
            logging.info("Reddit spoiler detected : [{}] {}".format(submission.id, submission.title))
            return True
        else:
            return False

    @staticmethod
    def remove_duplicates(images, confidence):
        """
        Compare image hashes between them to remove potential duplicates
        :param images: list of Image model object
        :param confidence: minimum distance between hashes to remove duplicates
        :return: initial list minus duplicates
        """
        copy_images = images
        for n, image in enumerate(images):
            descriptors = [i.descr for i in copy_images]
            for d, h in im_utils.get_closest_match(image, descriptors):
                if d < confidence and not d == 0:
                    del copy_images[n]
        return copy_images

    @staticmethod
    def is_duplicate(image, descriptors, confidence=29):
        """
        Test if phash has a near-duplicate hash in list
        :param phash: phash to compare
        :param phashes: list of phash
        :param confidence: minimal distance to be a duplicate
        :return: True if hash has a duplicate False if not
        """
        for d, h in im_utils.get_closest_match(image, descriptors, limit=10):
            if d < confidence:
                logging.info(f"{image} considered as duplicate.")
                return True
        return False

    def detect_set(self, text: str):
        """
        Test if text contain a set_code usually in between brackets at beginning of string
        :param text: String text to be tested
        :return: set_code (3 or 4 letters in lower_case)
        """
        reg = re.compile(self.reddit_set_reg)
        match = reg.findall(text)
        if match:
            return match[0].lower()
