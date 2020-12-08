import re
import config
import praw


class Reddit:
    search_limit = 20
    stream = False

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
