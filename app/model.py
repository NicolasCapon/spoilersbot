from datetime import datetime
from enum import Enum, auto
import scryfall
import config
import logging
from sqlalchemy import Column, Integer, String, DateTime, create_engine, BLOB
from sqlalchemy.orm import sessionmaker, relationship, scoped_session
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine(config.db, connect_args={'check_same_thread': False})
Base = declarative_base()


class Set(Base):

    __tablename__ = 'set'

    code = Column(String, primary_key=True)
    name = Column(String)
    released_at = Column(DateTime)
    card_count = Column(Integer)
    scryfall_id = Column(String)

    cards = relationship("Spoiler")

    def __repr__(self):
        return f"<Set(code={self.code}, name={self.name}, released_at={self.released_at}, "\
               f"card_count={self.card_count}, scryfall_id={self.scryfall_id})>"


class Image(Base):

    __tablename__ = 'image'

    id = Column(Integer, primary_key=True, autoincrement=True)
    location = Column(String)
    descr = Column(BLOB)
    conf = Column(Integer)

    spoiler = relationship("Spoiler", uselist=False)

    def __init__(self, location: str, descr=None):
        self.location = location
        self.descr = descr
        self.cv_array = None

    def __repr__(self):
        return f"<Image(id={self.id}, location={self.location}, conf={self.conf})>"


class Spoiler(Base):

    __tablename__ = 'spoiler'

    id = Column(Integer, primary_key=True, autoincrement=True)
    found_at = Column(DateTime, default=datetime.now())
    url = Column(String)
    source = Column(String)  # Domain
    source_id = Column(String)  # Reddit or scryfall id
    file_type = Column(String)  # Image / Video / Article

    image_id = Column(Integer, ForeignKey("image.id"))
    image = relationship(Image, uselist=False)

    set_code = Column(String, ForeignKey("set.code"))
    set = relationship(Set, uselist=False)

    def __repr__(self):
        return f"<Spoiler(id={self.id}, found_at={self.found_at}, url={self.url}, file_type={self.file_type}, "\
               f"source_id={self.source_id}, image_id={self.image_id}, set_code={self.set_code})>"


class SpoilerSource(Enum):
    REDDIT = "Reddit"  # "https://www.reddit.com/"
    SCRYFALL = "Scryfall"  # "https://scryfall.com/"
    MYTHICSPOILER = "Mythic Spoiler"  # "https://mythicspoiler.com/"


class FileType(Enum):
    IMAGE = auto()
    VIDEO = auto()
    ARTICLE = auto()


def import_scryfall_set(s, digital=None):
    local_session = Session()
    """Import scryfall Set to db, set digital to None to import all Sets"""
    if digital is None or s["digital"] == digital:
        local_session.add(Set(code=s["code"],
                              name=s["name"],
                              released_at=scryfall.to_datetime(s["released_at"]),
                              card_count=s["card_count"],
                              scryfall_id=s["id"]))
        return True


def update_sets():
    local_session = Session()
    sets_ref = [s.code for s in local_session.query(Set.code)]
    sets = [s for s in scryfall.get_set_list() if s["code"] not in sets_ref and not s["digital"]]
    s_cpt = 0
    for s in sets:
        if import_scryfall_set(s):
            s_cpt += 1
    local_session.commit()


Base.metadata.create_all(engine)
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

if __name__ == "__main__":
    update_sets()
