import config
import scryfall
import logging
import im_utils
from yolo import Yolo
from datetime import datetime, timedelta
from time import sleep
from reddit import Reddit
from mythicspoiler import MythicSpoiler
from model import Session, Spoiler, Image, SpoilerSource, Set, update_sets
from spoiler_detector import SpoilerDetector
from prawcore.requestor import RequestException


class SpoilerController:

    def __init__(self, updater):
        self.sd = SpoilerDetector()
        self.ms = MythicSpoiler()
        self.yolo = Yolo(config.model, config.classes, config.conf)
        self.reddit = Reddit(subreddit="magicTCG")
        self.scryfall_futur_cards_id = []
        self.reddit_futur_cards_subm_id = []
        self.mythicspoiler_futur_cards_url = []
        self.limit_days = 30
        # List of Spoiler Objects
        limit_date = datetime.today() - timedelta(days=self.limit_days)
        self.spoiled = Session.query(Spoiler).filter(Spoiler.found_at > limit_date).all()
        # Job queues:
        updater.job_queue.run_repeating(self.general_crawl, interval=60, first=10)

    def general_crawl(self, context):
        self.update_db(context)
        self.flush_old_spoilers()
        self.scryfall_cards_crawl(context)
        self.mythicspoiler_crawl(context)
        self.reddit_crawl(context)

    def scryfall_cards_crawl(self, context):
        local_session = Session()
        futur_cards = scryfall.get_futur_cards()
        for futur_card in futur_cards:
            if not futur_card.get("id") in self.scryfall_futur_cards_id:
                logging.info(f"New card detected from scryfall: {futur_card.get('name')}")
                # New card detected, add it to scryfall list
                self.scryfall_futur_cards_id.append(futur_card.get("id"))
                # Try to see if it has already been spoiled
                for i_url in scryfall.get_image_urls(futur_card):
                    im = Image(location=i_url,
                               descr=im_utils.descript_image(i_url))
                    if not self.sd.is_duplicate(im, [s.image.descr for s in self.spoiled]):
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
                        self.send_spoiler(sp, context)
        local_session.commit()

    def mythicspoiler_crawl(self, context):
        local_session = Session()
        for s in scryfall.get_futur_sets():
            cards = self.ms.get_cards_from_set(s.get("code"))
            for page, image_url in cards:
                if image_url not in self.mythicspoiler_futur_cards_url:
                    logging.info(f"New card detected from mythicspoiler: {page}")
                    # New card detected on mythic spoiler, save it
                    self.mythicspoiler_futur_cards_url.append(image_url)
                    # Try to see if it has already been spoiled
                    im = Image(location=image_url,
                               descr=im_utils.descript_image(image_url))
                    if not self.sd.is_duplicate(im, [s.image.descr for s in self.spoiled]):
                        # card not recognize as a duplicate, save then publish it
                        local_session.add(im)
                        sp = Spoiler(url=page,
                                     source=self.ms.url,
                                     source_id=self.ms.url,
                                     found_at=datetime.now())
                        sp.image = im
                        sp.set = local_session.query(Set).filter(Set.code == s.get("code")).first()
                        local_session.add(sp)
                        self.spoiled.append(sp)
                        self.send_spoiler(sp, context)
        local_session.commit()

    def reddit_crawl(self, context):
        local_session = Session()
        try:
            submissions = self.reddit.subreddit.new()
        except RequestException as e:
            logging.error(e)
            submissions = []
        for submission in submissions:
            if submission in self.reddit_futur_cards_subm_id or not self.sd.is_reddit_spoiler(submission):
                continue
            self.reddit_futur_cards_subm_id.append(submission)
            link = "https://www.reddit.com" + submission.permalink
            logging.info(f"New card spoiler submission from reddit: {link}")
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
                for image, confidence in subspoilers:
                    i = Image(location=image_url,
                              descr=im_utils.descript_image(image))
                    i.cv_array = image
                    local_session.add(i)
                    subspoilers_images.append(i)
            logging.info(f"Yolo found {len(subspoilers_images)} cards on {len(images)} images.")
            # Remove potentiel duplicate within the submission itself
            subspoilers_images = self.sd.remove_duplicates(subspoilers_images, confidence=30)
            logging.info(f"Remove duplicate in self, list down to {len(subspoilers_images)} cards after filtration.")

            set_code = self.sd.detect_set(submission.title)
            s = local_session.query(Set).filter(Set.code == set_code).first()
            # For each image, test if descriptor is in spoiled card, if not create spoiler
            sub_spoiler = []
            for image in subspoilers_images:
                if not self.sd.is_duplicate(image, [s.image.descr for s in self.spoiled]):
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
                    logging.info("Filtration found a duplicate in DB.")
            # Create a message with reddit submission link then send images only
            if len(sub_spoiler):
                text = f"{len(sub_spoiler)} new spoiler(s) found on <a href='{link}'>reddit</a> !"
                context.bot.send_message(chat_id=config.chat_id,
                                         text=text,
                                         parse_mode="HTML",
                                         disable_web_page_preview=True)
                for spoil in sub_spoiler:
                    self.send_spoiler(spoil, context)
            local_session.commit()

    @staticmethod
    def send_spoiler(spoiler: Spoiler, context):
        logging.info(f"Send spoiler {spoiler} to channel.")
        if spoiler.image.cv_array is not None:
            # Send photo directly if image is open_cv array
            caption = None
            if spoiler.set:
                caption = f"\nfrom {spoiler.set.name}\n<i>confidence = {spoiler.image.conf}%</i>"
            context.bot.send_photo(chat_id=config.chat_id,
                                   photo=im_utils.get_file_from_cv_image(spoiler.image.cv_array),
                                   caption=caption,
                                   parse_mode="HTML")
        else:
            text = f"<a href='{spoiler.image.location}'>New spoiler</a> detected !"\
                   f"\n<i>confidence = {spoiler.image.conf}%</i>"
            # Send url in message text
            context.bot.send_message(chat_id=config.chat_id,
                                     text=text,
                                     parse_mode="HTML")
        # Avoid spam
        sleep(0.1)

    @staticmethod
    def update_db(context):
        update_sets()

    def flush_old_spoilers(self):
        for spoiler in self.spoiled:
            if spoiler.found_at < datetime.today() - timedelta(days=self.limit_days):
                self.spoiled.remove(spoiler)
