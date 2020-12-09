# Spoilers Bot
## Summary
Spoilers Bot is a Telegram bot written in python who aims at collecting all new revealed MTG cards and displaying them in one channel.
The bot is currently plugged on 3 main sources of new cards :
- [Scryfall](https://scryfall.com/)
- [MythicSpoiler](https://mythicspoiler.com/)
- [r/magicTCG](https://www.reddit.com/r/magicTCG/) on reddit

It crawls those sites in order to find cards that can potentially be new.

## Install
### Prerequisite
In order to deploy your own **spoilers bot** you need to have:
- [Docker](https://www.docker.com/) and docker-compose on your machine.
- A Yolo v4 detection model (.weights file)
- A telegram account (id) and a telegram bot token
- A reddit api account (tokens app)

### Deployement
Once you have all the requirements:
1. Clone the repository
```
git clone https://github.com/NicolasCapon/spoilersbot.git
cd spoilersbot/
```
2. Rename config.py.example to config.py then fill the file with your credentials
3. Paste the yolo v4 .weights file into app/yolo/ directory
4. Build the docker image and run a container
```
sudo docker-compose up --build spoilersbot
```
The bot should send you "Bot started" when is up.

## How does it works ?
The main detection is based on image recognition. The bot calculates and stores a descriptor for each card image.
Then each new revealed card is compared to the stored descriptors resulting in a list of similarity scores. We then take the minimum value of this list and test it against a threshold (empiric value). If the card is too similar we discard it, otherwise it's considered as a new card and it's sent to the chat and stored in database.

Currently, the bot uses image histograms to compute similarity score (phash was first used without any good result).

The other part is the yolo v4 machine learning algorithm used on the reddit crawl. Nowadays a lot of spoilers are served on reddit in batches, which means a single image can contains 2 to 4 images of new cards, sometimes even more with a background. These types of images can't be compared as it is because we compare single card images. The yolo model was built to detect cards on a image and extract them. The result of a image containing 4 cards is now 4 images of the cards themselves ready to be compared.

## Yolo v4 image detection

### Tackle the problem
I trained a [YOLO v4](https://arxiv.org/abs/2004.10934) model to solve images like this:
![](https://i.redd.it/lef7sla7l6x51.jpg)
Those are impossible to compare to normal card image in terms of similarities.
I first try to solve this problem with regular image processing methods, but with extended art cards like the one on the right, the edge is even harder to find. Moreover the diversity of possible backgrounds makes the task too hard.
That's why I trained a machine learning model to detect MTG card in image.

### Training
TODO

### Results
TODO

## Image Similarity
TODO
