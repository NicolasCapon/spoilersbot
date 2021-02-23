import config
import scryfall
import im_utils
import model_cv
import time
from typing import List
from yolo import Yolo
from datetime import datetime, timedelta
from time import sleep
from reddit import Reddit
from mythicspoiler import MythicSpoiler
from model import Session, Spoiler, Image, SpoilerSource, Set, update_sets
from prawcore.requestor import RequestException


class SpoilerController:

    def __init__(self, updater):
        self.updater = updater
        self.comparator = model_cv.OrbComparator()
        self.ms = MythicSpoiler()
        self.yolo = Yolo(config.model, config.classes, config.conf)
        self.reddit = Reddit(subreddit="magicTCG")
        self.scryfall_futur_cards_id = []
        self.reddit_futur_cards_subm_id = []
        self.mythicspoiler_futur_cards_url = []
        self.limit_days = 7
        # List of Spoiler Objects
        limit_date = datetime.today() - timedelta(days=self.limit_days)
        self.spoiled: List[Spoiler] = Session.query(Spoiler).filter(Spoiler.found_at > limit_date).all()
        self.general_crawl()

    def general_crawl(self):
        print("loop started")
        while True:
            s = time.process_time()
            self.update_db()
            self.flush_old_spoilers()
            self.reddit_crawl()
            # self.scryfall_cards_crawl()
            self.mythicspoiler_crawl()
            d = time.process_time() - s
            # Ensure that a crawl is done every minute at minimum
            if d < config.crawl_frequency:
                time.sleep(config.crawl_frequency - d)

    def scryfall_cards_crawl(self):
        local_session = Session()
        futur_cards = scryfall.get_futur_cards()
        for futur_card in futur_cards:
            if not futur_card.get("id") in self.scryfall_futur_cards_id:
                config.bot_logger.info(f"New card detected from scryfall: {futur_card.get('name')}")
                # New card detected, add it to scryfall list
                self.scryfall_futur_cards_id.append(futur_card.get("id"))
                # Try to see if it has already been spoiled
                for i_url in scryfall.get_image_urls(futur_card):
                    im = Image(location=i_url, comparator=self.comparator)
                    if not self.comparator.is_duplicate(im, [s.image for s in self.spoiled]):
                        # card not recognize as a duplicate, save then publish it
                        local_session.add(im)
                        sp = Spoiler(url=scryfall.get_card_url(futur_card),
                                     source=SpoilerSource.SCRYFALL.value,
                                     source_id=futur_card.get("id"),
                                     found_at=datetime.now(),
                                     set_code=futur_card.get("set_code", None))
                        sp.image = im
                        local_session.add(sp)
                        self.spoiled.append(sp)
                        sp.set = local_session.query(Set).filter(Set.code == futur_card.get("set_code")).first()
                        self.send_spoiler(sp)
        local_session.commit()

    def mythicspoiler_crawl(self):
        local_session = Session()
        cards = self.ms.get_cards_from_news(max_days=self.limit_days)
        for page, image_url, card_set in cards:
            if image_url not in self.mythicspoiler_futur_cards_url:
                config.bot_logger.info(f"New card detected from mythicspoiler: {page}")
                # New card detected on mythic spoiler, save it
                self.mythicspoiler_futur_cards_url.append(image_url)
                # Try to see if it has already been spoiled
                im = Image(location=image_url, comparator=self.comparator)
                if not self.comparator.is_duplicate(im, [s.image for s in self.spoiled]):
                    print(im)
                    # card not recognize as a duplicate, save then publish it
                    local_session.add(im)
                    sp = Spoiler(url=page,
                                 source=SpoilerSource.MYTHICSPOILER.value,
                                 found_at=datetime.now(),
                                 set_code=card_set)
                    sp.image = im
                    sp.set = local_session.query(Set).filter(Set.code == card_set).first()
                    local_session.add(sp)
                    self.spoiled.append(sp)
                    self.send_spoiler(sp)
        local_session.commit()

    def reddit_crawl(self):
        local_session = Session()
        try:
            submissions = self.reddit.subreddit.new()  # [self.reddit.reddit.submission(id="lmzn2m")]
        except RequestException as e:
            config.bot_logger.error(e)
            submissions = []
        for submission in submissions:
            if submission in self.reddit_futur_cards_subm_id or not self.reddit.is_spoiler(submission):
                continue
            self.reddit_futur_cards_subm_id.append(submission)
            link = "https://www.reddit.com" + submission.permalink
            config.bot_logger.info(f"New card spoiler submission from reddit: {link}")
            # Got a spoiler
            images = []
            # Crawl images from submission
            if hasattr(submission, "is_gallery"):
                for key, value in submission.media_metadata.items():
                    images.append(value.get("s", {}).get("u"))
            elif hasattr(submission, "preview"):
                images.append(submission.preview.get("images", [])[0].get("source").get("url"))

            # Use YOLOv4 model to detect if image is composed of multiple cards
            subspoilers_images = []
            for image_url in images:
                subspoilers = self.yolo.get_detected_objects(image_url)
                for image, _ in subspoilers:
                    i = Image(location=image_url, comparator=self.comparator, cv_array=image)
                    # i.cv_array = image
                    local_session.add(i)
                    subspoilers_images.append(i)
            config.bot_logger.info(f"Yolo found {len(subspoilers_images)} cards on {len(images)} images.")
            # Remove potentiel duplicate within the submission itself if multiple cards detected
            if len(subspoilers_images) > 1:
                subspoilers_images = self.comparator.remove_duplicates(subspoilers_images)
                config.bot_logger.info(f"Remove duplicate in self, list down to {len(subspoilers_images)} cards after filtration.")

            set_code = self.reddit.detect_set(submission.title)
            s = local_session.query(Set).filter(Set.code == set_code).first()
            # For each image, test if descriptor is in spoiled card, if not create spoiler
            sub_spoiler = []
            for image in subspoilers_images:
                if not self.comparator.is_duplicate(image, [s.image for s in self.spoiled]):
                    sp = Spoiler(url=link,
                                 source=SpoilerSource.REDDIT.value,
                                 source_id=submission.id,
                                 found_at=datetime.now())
                    sp.image = image
                    if s:
                        sp.set = s
                    local_session.add(sp)
                    self.spoiled.append(sp)
                    sub_spoiler.append(sp)
                else:
                    config.bot_logger.info("Filtration found a duplicate in DB.")
            # Create a message with reddit submission link then send images only
            if len(sub_spoiler):
                for spoil in sub_spoiler:
                    self.send_spoiler(spoil)
            local_session.commit()

    def send_spoiler(self, spoiler: Spoiler):
        config.bot_logger.info(f"Send spoiler {spoiler} to channel.")
        set_text = ""
        if spoiler.set:  # https://scryfall.com/sets/aer
            if spoiler.source == SpoilerSource.MYTHICSPOILER.value:
                set_url = f"http://mythicspoiler.com/{spoiler.set.code}/index.html"
            else:
                set_url = f"https://scryfall.com/sets/{spoiler.set.code}"
            set_text += f"from <a href='{set_url}'>{spoiler.set.name}</a> "
        caption = f"New spoiler {set_text}!\nSource: <a href='{spoiler.url}'>{spoiler.source}</a>"
        if spoiler.image.cv_array is not None:
            # Send photo directly if image is open_cv array
            self.updater.bot.send_photo(chat_id=config.chat_id,
                                        photo=im_utils.get_file_from_cv_image(spoiler.image.cv_array),
                                        caption=caption,
                                        parse_mode="HTML")
        else:
            # Send url in message text
            self.updater.bot.send_photo(chat_id=config.chat_id,
                                        photo=spoiler.image.location,
                                        caption=caption,
                                        parse_mode="HTML")
        # Avoid spam
        sleep(0.1)

    @staticmethod
    def update_db():
        # TODO: for upcoming set, update infos like release date and card count...
        # -> can improve the send spoiler method to include set infos on release
        update_sets()

    def flush_old_spoilers(self):
        for spoiler in self.spoiled:
            if spoiler.found_at < datetime.today() - timedelta(days=self.limit_days):
                self.spoiled.remove(spoiler)
