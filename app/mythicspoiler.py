import os
import re
import requests
from bs4 import BeautifulSoup, Comment, Tag, NavigableString


class MythicSpoiler:
    """Class specifically designed to extract card and set info on mythicspoiler.com"""

    url = "https://mythicspoiler.com/"
    page_reg = r'cards\/.*\.html|jpg|png$'  # reg to find all card pages
    img_reg = r'cards\/.*\.jpg|png$'  # reg to find all card images
    # Card types figuring on card page:
    card_types = {"CARD NAME": "name",
                  "MANA COST": "cmc",
                  "TYPE": "type",
                  "CARD TEXT": "text",
                  "FLAVOR TEXT": "flavor",
                  "ILLUS": "artist",
                  "Set Number": "set_num",
                  "P/T": "p/t"}

    def get_cards_from_news(self):
        """
        Fetch /newspoilers.html and return all cards
        :return: list of tuple (card_url, card_image_url, expansion)
        """
        r = requests.get(self.url + "newspoilers.html")
        if r.ok:
            soup = BeautifulSoup(r.text, 'html.parser')
        else:
            return []
        tags = soup.find_all('a', {'href': re.compile(self.page_reg)})
        cards = []
        for tag in tags:
            page = self.url + tag.get("href", "").replace("\n", "")
            image_url = None
            if ".html" not in os.path.splitext(tag.get("href"))[1]:
                page = None
            if tag.img:
                image_url = self.url + tag.img.get("src", "").replace("\n", "")
            if page:
                reg = re.compile("https://mythicspoiler\.com\/(.*)\/cards/")
                match = reg.findall(page)
                if len(match):
                    expansion = match[0]
                else:
                    expansion = None
            if image_url:
                cards.append((page, image_url, expansion))
        return cards

    def get_cards_from_set(self, set_code):
        """ Return tuple (page_url, image_url)
            page_url = mythicspoiler page url for this card if not : None
            image_url = link to card image
        """
        set_code = set_code.lower()
        r = requests.get(self.url + set_code)
        if r.ok:
            soup = BeautifulSoup(r.text, 'html.parser')
        else:
            return []
        tags = soup.find_all('a', {'href': re.compile(self.page_reg)})
        cards = []
        for tag in tags:
            page = os.path.join(set_code, tag.get("href"))
            if not os.path.splitext(tag.get("href"))[1] == ".html":
                page = None
            image_url = tag.img.get("src")
            cards.append((page, image_url))
        return cards

    def get_card_info(self, card_url):
        """Extract card info from card url (mythicspoiler)"""
        infos = {}
        # Extract only html containing card info
        reg = r"<!--CARD TEXT-->(\n|.)*<!--END CARD TEXT-->"
        r = requests.get(self.url + card_url)
        if r.ok:
            p = re.compile(reg)
            result = p.search(r.text)
            if result:
                text = result.group(0)
            else:
                return None

        soup = BeautifulSoup(text, 'html.parser')
        # Remove br elements
        for e in soup.findAll('br'):
            e.extract()
        for c in soup.contents:
            if isinstance(c, Tag):
                comments = c.findAll(text=lambda t: isinstance(t, Comment))
                for comment in comments:
                    if comment in self.card_types.keys():
                        info = ""
                        v = comment.next_element
                        # Sometimes one info is spread between multiple NavigableString
                        while isinstance(v, NavigableString) \
                                and "END CARD" not in v.string \
                                and v.string not in self.card_types.keys():
                            info += re.sub(pattern=r'(^(?:\\n)+|(?:\\n)+$)', repl='', string=v.string)
                            v = v.next_element
                        # prettify result
                        info = re.sub(pattern=r'(^(?:\n)+|(?:\n)+$)', repl='', string=info.strip())
                        info = re.sub(pattern=r'(\n)+', repl='\n', string=info)
                        infos[self.card_types[comment]] = info
        return infos


if __name__ == "__main__":
    m = MythicSpoiler()
    c = m.get_cards_from_news()  # ['tsr', 'cc1']
    print(c)
