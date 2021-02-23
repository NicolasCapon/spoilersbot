import config
import praw
import re


class Reddit:
    search_limit = 20
    stream = False
    reddit_set_reg = r"^\[(.{3,4})\]"
    flairs = ["Spoiler", "News"]
    domain = "self.magicTCG"

    def __init__(self, subreddit=None, read_only=True):
        self.reddit = praw.Reddit(client_id=config.client_id,
                                  client_secret=config.client_secret,
                                  password=config.password,
                                  user_agent=config.user_agent,
                                  username=config.username)
        self.reddit.read_only = read_only
        self.subreddit = subreddit
        if subreddit:
            self.subreddit = self.reddit.subreddit(subreddit)

    def search_spoilers(self):
        return self.subreddit.search('flair:"spoiler"', limit=self.search_limit)

    def browse_news(self, func, *args, **kwargs):
        for submission in self.reddit.subreddit("magicTCG").new():
            func(submission, *args, **kwargs)

    def browse_hots(self, func, *args, **kwargs):
        for submission in self.reddit.subreddit("magicTCG").hot():
            func(submission, *args, **kwargs)

    def stream_subreddit(self, func, *args, **kwargs):
        if self.subreddit:
            for submission in self.subreddit.stream.submissions():
                func(submission, *args, **kwargs)

    def is_spoiler(self, submission):
        """
        Test if a reddit submission can be considered as a spoiler
        :param submission: PRAW submission object
        :return: True if submission is spoiler, False if not
        """
        # Discard any submission containing no external link to a potential spoiler
        if submission.domain == self.domain:
            return False
        # If submission is flaired or tag as spoiler:
        elif submission.spoiler or submission.link_flair_text in self.flairs:
            if submission.link_flair_text == "News" and not self.detect_set(submission.title):
                # If submission is a news and dont comport the set code in between brackets, rejects it
                return False
            log = f"Reddit spoiler detected (flair={submission.link_flair_text}): [{submission.id}] {submission.title}"
            config.bot_logger.info(log)
            return True
        else:
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


if __name__ == "__main__":
    from yolo import Yolo
    from spoiler_detector import SpoilerDetector
    model = "/home/ubuntu/Desktop/yolo_custom_detection/yolov4_custom_train_last.weights"
    classes = ["card"]
    conf = "/home/ubuntu/Desktop/yolo_custom_detection/yolov4_custom_test.cfg"
    y4 = Yolo(model, classes, conf)
    sd = SpoilerDetector()
    r = Reddit(subreddit="magicTCG")
    r.browse_news(sd.is_reddit_spoiler)

    # is_reddit_spoiler(r.reddit.submission(id="fwn9eo"))
