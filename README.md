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

### Create a proper training dataset
Since the goal is to detect new cards in an image, i started to look on reddit for the lastly revealed cards.
On reddit, cards are commonly revealed with "spoiler" flair and a title including the card set code in between bracket. 
For the image below, corresponding title was ["[CMR] Akroma, Vision of Ixidor and Akroma's Will (Source: Ashlen Rose on YT)"](https://www.reddit.com/r/magicTCG/comments/jnswxw/cmr_akroma_vision_of_ixidor_and_akromas_will/)
With those search criterias I gathered approximately 30 images and started labelling them with [labelImg](https://github.com/tzutalin/labelImg).
The task was really tedious and I needed 10 times more images at least. That's why I started to think about generating synthetic datas.
Since all these images were not photos or real object, generating images of random cards onto a background was the trick to lazyly create thousands of images and boxes indicating positions of the cards inside.

You can find in [yolo.py](https://github.com/NicolasCapon/spoilersbot/blob/master/app/yolo.py) the algorithm I used to generate the dataset.
Basically the steps are:
1. Pick random cards with the modern MTG layout (to have images as close as possible to the modern card design)
2. Use the illustration of one of them as background
3. Overlay 2 to 4 cards onto the background
4. Save the image and the file indicating coordinates of the cards

With this method, I produced over 3000 images and labels.

### Training a model
To solve this problem I picked yolo for differents reasons:
- The algorithm was designed to detect objects in image
- Since I'm working on a raspberry pi I needed something compatible and not to heavy
- Lot of tutorials and supports are available online, and it's my first go on artificial intelligence algorithms.
- It can be used on [Google Collab](https://colab.research.google.com/) a free online plateform that let's you train models for 24h.

As a first dive into AI training, I used [Pysource video](https://www.youtube.com/watch?v=_FNfRtXEbr4&t) to learn the basics. Thanks to this video I had a google collab notebook ready to train my model with yolo v3 and a quick python script to test it.
I managed to get the job done but realized I can upgrade to yolo v4. I tweaked the notebook ([which can be find here](https://github.com/NicolasCapon/spoilersbot/blob/master/app/yolo/Train_YoloV4_.ipynb)) and trained it for as long as possible, resulting in over 6000 iterations.

### Results
Comparing to classic image processing method, the AI is by far superior:
- It can detects if an image contains no cards
- Cards with no edge are now detected with accuracy
- Even images showing only a card itself are classified as cards
The only downside is that sometimes some rectangles are detected as cards. But since all cards have the same width and height, I solved this issue by discarding all rectangles with a wrong size ratio, reducing significantly the number of false positives.

I trained few models before this one, with less images and less time.
With approximately 1000 images and and 3h of training, the results were poor, especially on extended art cards. That's why I started included them in the dataset by a good amount.

## Image Similarity

### Why using it ?
Since I'm using 3 different sources for new cards, the bot gonna encounter lots of duplicate we dont want to see on the channel. Even on a source like Reddit, a card can be published multiple times.

### How to compare images
This subject is large and difficult but in general you want to choose :
- a way to descript your images
- a way mesure the distance between descriptors.

My first idea was to use [perceptual hashing](https://en.wikipedia.org/wiki/Perceptual_hashing) because it's fast and I saw a lot of projects using this strategy. But after many tests, the result were not concluant enough. A bunch of images with a same dominant color were showing a similarity score as if they were the same card. Even when I was comparing only illustrations.
I choosed to take a more ressources heavy method, histograms. Histograms show the repartition of each color within the image and they can be compared to each other.
This method show more reliant results but is also slower than hashing. In our case, the computational time is not what matter the most, the accuracy is. Moreover, the population of candidate for duplicates is rather small (around 300 cards) because I make sure to remove candidates that are to old (all cards detected for more than one month are discarded).

Other comparison methods could also be considered like:
- [Feature Matching with FLANN](https://docs.opencv.org/3.4/d5/d6f/tutorial_feature_flann_matcher.html) who aims at finding gradient to describe images
- [Bags of words](https://towardsdatascience.com/bag-of-visual-words-in-a-nutshell-9ceea97ce0fb) who search for common features in images

For now I will stick with histogram comparaison because I lack of results to see if this method is enough to solve most of duplicates. Also the implementation is quite easy. But there is tons of improvements that can be considered.

## TODO
- Improve log (daily file)
- Improve Mythic spoiler detector
- Test Orb comparaison instead of histograms:
    - Create class crawl/probe to connect new source ?
