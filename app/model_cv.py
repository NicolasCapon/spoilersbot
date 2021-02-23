from __future__ import annotations
from typing import List, Any, Union
from numpy import ndarray, frombuffer, reshape
from abc import ABC, abstractmethod
from cv2 import ORB_create, BFMatcher, calcHist, compareHist, normalize, HISTCMP_BHATTACHARYYA
from distance import hamming
from PIL import Image as PILImage
from imagehash import phash
import pickle

Descriptor = Any
Distance = Union[int, float]


class Image(ABC):

    @property
    def location(self) -> str:
        """
        Location of the image
        :return: str
        """
        pass

    @property
    def descriptor(self):
        """
        Description of the image.
        :return: Any
        """
        pass

    @abstractmethod
    def get_illustration(self) -> ndarray:
        """
        Get image in open_cv format
        :return: ndarray image
        """
        pass

    @abstractmethod
    def __init__(self, location, comparator: ImageComparator = None):
        pass


Album = List[Image]


class ImageComparator(ABC):

    @property
    def method(self) -> str:
        """
        Method used to compare images
        :return: str
        """
        pass

    @abstractmethod
    def descript_image(self, image: Image) -> Descriptor:
        """
        Descript the image with given method
        :param image: Image object
        :return: a description of the image
        """
        pass

    @abstractmethod
    def get_closest_matches(self, ref: Image, album: Album, limit: int = 1) -> List[(Distance, Image)]:
        """
        Get the closest images from given Image
        :param ref: Image to search
        :param album: Image to compare against ref
        :param limit: int length of results to be returned
        :return: List[(distance, Image)] list of tuple containing the distance between this image and the reference
        """
        pass

    @abstractmethod
    def is_duplicate(self, ref: Image, album: Album) -> bool:
        """
        Check for duplicate of the ref Image in list of Images using a tolerance threshold
        :param ref: Image to search
        :param album: Image to compare against ref
        :return: bool True if ref image considered in the album, False if not
        """
        pass
    
    @abstractmethod
    def remove_duplicates(self, album: Album) -> Album:
        """
        Compare image descriptors between them to remove potential duplicates
        :param album: list of Image model object
        :return: initial list minus duplicates
        """
        pass


class OrbComparator(ImageComparator):
    method = "ORB"

    def __init__(self, lowe_ratio: float = 0.6, threshold: int = 10):
        self._finder = ORB_create()
        self._matcher = BFMatcher()
        self._lowe_ratio = lowe_ratio
        self._threshold = threshold

    def descript_image(self, image: Image) -> ndarray:
        return pickle.dumps(self._finder.detectAndCompute(image.get_illustration(), None)[1])

    def get_closest_matches(self, ref: Image, album: Album, limit=1):
        matches = []
        for img in album:
            poi = self._matcher.knnMatch(queryDescriptors=pickle.loads(ref.descriptor),
                                         trainDescriptors=pickle.loads(img.descriptor),
                                         k=2)
            good_poi_num = len([[m] for m, n in poi if m.distance < self._lowe_ratio * n.distance])
            matches.append((good_poi_num, img))
        return sorted(matches, reverse=True, key=lambda x: x[0])

    def is_duplicate(self, ref: Image, album: Album) -> bool:
        if album and (m := self.get_closest_matches(ref, album)):
            return m[0][0] >= self._threshold

    def remove_duplicates(self, album: Album) -> Album:
        unique_album = []
        for i in range(len(album)):
            image = album.pop()
            if not self.is_duplicate(image, album):
                unique_album.append(image)
        return unique_album


class HistogramComparator(ImageComparator):

    method = "Histogram"

    def __init__(self, threshold: float = 0.29):
        self.comp = HISTCMP_BHATTACHARYYA
        self._threshold = threshold

    def descript_image(self, image: Image):
        hist = calcHist([image.get_illustration()], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        return normalize(hist, hist).flatten()

    def get_closest_matches(self, ref: Image, album: Album, limit=1):
        distances = sorted([(compareHist(ref.descriptor,
                                         frombuffer(img, dtype=ref.descriptor.dtype),
                                         self.comp) * 100,
                             frombuffer(img, dtype=ref.descriptor.dtype))
                            for img in album],
                           key=lambda x: x[0])[:limit]
        return distances

    def is_duplicate(self, ref: Image, album: Album) -> bool:
        self.get_closest_matches(ref, album)[0] >= self._threshold

    def remove_duplicates(self, album: Album, confidence) -> Album:
        copy_album = album
        for n, image in enumerate(album):
            descriptors = [i.descr for i in copy_album]
            for d, h in self.get_closest_matches(image, descriptors):
                if d < confidence and not d == 0:
                    del copy_album[n]
                    break
        return copy_album


class HashComparator(ImageComparator):

    method = "Perceptual Hashing"

    def __init__(self, hash_size: int = 16, threshold: float = 0.29):
        self._hash_size = hash_size
        self._threshold = threshold

    def descript_image(self, image):
        return str(phash(PILImage.fromarray(image.get_illustration()), hash_size=self.hash_size))

    def get_closest_matches(self, ref: Image, album: Album, limit=1):
        return sorted([(hamming(ref.descriptor, i.descriptor), i) for i in album], key=lambda x: x[0])[:limit]

    def is_duplicate(self, ref: Image, album: Album) -> bool:
        self.get_closest_matches(ref, album)[0] >= self._threshold

    def remove_duplicates(self, album: Album, confidence) -> Album:
        copy_album = album
        for n, image in enumerate(album):
            descriptors = [i.descr for i in copy_album]
            for d, h in self.get_closest_matches(image, descriptors):
                if d < confidence and not d == 0:
                    del copy_album[n]
                    break
        return copy_album