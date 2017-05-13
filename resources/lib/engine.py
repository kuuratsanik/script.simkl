#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
import xbmc
import interface
import utils
from datetime import datetime
from utils import getstr
import json
__addon__ = interface.__addon__

class Engine:
  """ Like an offline api class """
  def __init__(self, api, player):
    self.api = api
    self.player = player
    player.engine = self
    player.api    = api

  #Note 4 myself: Maybe you should handle movies and series completly different
  #I mean: Two different functions, two different "databases", etc.
  def synclibrary(self, mode="full"):
    """ Syncs simkl with kodi """
    simkl_old_f = utils.get_old_file("simkl")
    kodi_old_f = utils.get_old_file("kodi")
    kodi_current = {
      "movies": self.get_movies("1+"),
      "movies_0": self.get_movies("0"),
      #"episodes": self.get_episodes(),
      "lastcheck": datetime.today().strftime(utils.SIMKL_TIME_FORMAT)}
    simkl_current = self.api.get_all_items()
    # with open("/home/davo/.kodi/userdata/addon_data/script.simkl/current_simkl.json", "r") as f:
    #   simkl_current = json.loads(f.read())
    # with open("/home/davo/.kodi/userdata/addon_data/script.simkl/old_simkl.json", "r") as f:
    #   simkl_old = json.loads(f.read())

    def open_file(filename, current):
      """ Reads and overwrites files """
      if not os.path.exists(filename):
      #if True:
        with open(filename, "w") as f:
          f.write(json.dumps(current, indent=2))
        old = current.copy()
        old["movies_0"] = {}
        return old
      else:
        with open(filename, "r") as f:
          old = json.loads(f.read())
        with open(filename, "w") as f:
          f.write(json.dumps(current, indent=2))
        return old

    kodi_old = open_file(kodi_old_f, kodi_current)
    simkl_old = open_file(simkl_old_f, simkl_current)

    simkl_lastcheck = utils.simkl_time_to_kodi(self.api.get_last_activity()["movies"]["all"])
    if utils.getSetting("synclib"):
      if utils.getSetting("movie-sync"):
        self.syncmovies(simkl_old["movies"], simkl_current["movies"], kodi_old["movies"], \
         kodi_current["movies"], kodi_current["movies_0"], kodi_old["movies_0"], kodi_old["lastcheck"], simkl_lastcheck)

    lstchk_anime = self.api.get_last_activity()["anime"]["all"]
    lstchk_tv_shows = self.api.get_last_activity()["tv_shows"]["all"]
    simkl_lastcheck = max(lstchk_anime, lstchk_tv_shows)

  def syncmovies(self, simkl_old, simkl_current, kodi_old, kodi_current, \
    kodi_current_0, kodi_old_0, kodi_lastcheck, simkl_lastcheck):
    """ Syncs movies with simkl """
    simkl_lastcheck = utils.simkl_time_to_kodi(self.api.get_last_activity()["movies"]["completed"])
    xbmc.log("Simkl: Lastcheck movies %s" % simkl_lastcheck)

    simkl_added = self.diff(utils.simkl2kodi(simkl_old), utils.simkl2kodi(simkl_current))
    simkl_removed = self.diff(utils.simkl2kodi(simkl_current), utils.simkl2kodi(simkl_old))
    kodi_watched = self.diff(kodi_old, kodi_current)
    kodi_unwatched = self.diff(kodi_current, kodi_old)
    kodi_added = self.diff(kodi_old_0, kodi_current_0)
    #We can ignore items removed from library

    xbmc.log("kodi_unwatched %s, %s" % kodi_unwatched)
    xbmc.log("kodi_added %s, %s" % kodi_added)
    movies_to_simkl = []

    for movie in self.get_movies("0+"):
      #xbmc.log("Movie: %s" % movie)
      if movie["imdbnumber"] in simkl_added[1] and movie["imdbnumber"] not in kodi_unwatched[1]:
        xbmc.log("Added %s" % movie)
        movie["playcount"] = 1
        self.update_movie(movie)
      elif movie["imdbnumber"] in simkl_removed[1] and movie["imdbnumber"] not in kodi_watched[1]:
        xbmc.log("Removed %s" % movie)
        movie["playcount"] = 0
        self.update_movie(movie)
      elif movie["imdbnumber"] in kodi_watched[1] and movie["imdbnumber"] not in simkl_removed[1]:
        movie["playcount"] = 1
        movies_to_simkl.append(movie)
      elif movie["imdbnumber"] in kodi_unwatched[1] and movie["imdbnumber"] not in simkl_added[1]:
        movie["playcount"] = 0
        movies_to_simkl.append(movie)

      elif movie["imdbnumber"] in simkl_added[1] and movie["imdbnumber"] in kodi_unwatched[1]:
        xbmc.log("Conflicting %s" % movie)
        if simkl_lastcheck >= kodi_lastcheck:
          movie["playcount"] = 1
        else:
          movie["playcount"] = 0
        movies_to_simkl.append(movie)
        self.update_movie(movie)
      elif movie["imdbnumber"] in kodi_watched[1] and movie["imdbnumber"] in simkl_removed[1]:
        xbmc.log("Conflicting %s" % movie)
        if simkl_lastcheck >= kodi_lastcheck:
          movie["playcount"] = 0
        else:
          movie["playcount"] = 1
        movies_to_simkl.append(movie)
        self.update_movie(movie)
      elif movie["imdbnumber"] in kodi_added[1]:
        self.watch_if_kodi(movie)

    if len(movies_to_simkl) > 0: self.api.update_movies(movies_to_simkl)

  def watch_if_kodi(self, movie):
    """ Marks a movie as watched if is watched in kodi """
    c = self.api.check_if_watched(movie)
    xbmc.log("Movie, c: %s, %s" % (movie, c))
    if c:
      movie["playcount"] = 1
      self.update_movie(movie)

  @staticmethod
  def diff(A, B):
    """
      Returns the difference between A and B. About data return: B > A
    """
    A_movies = set([x["imdbnumber"] for x in A])
    B_movies = set([x["imdbnumber"] for x in B])
    diff = B_movies - A_movies
    return [movie_B for movie_B in B if movie_B["imdbnumber"] in diff], diff

  '''
  @staticmethod
  def sym_diff(A, B):
    """ Return the symetric difference between A and B """
    A_movies = set([x["imdbnumber"] for x in A])
    B_movies = set([x["imdbnumber"] for x in B])
    diff1 = B_movies - A_movies
    diff2 = A_movies - B_movies
    symet = diff1 | diff2

    [movie_B for movie_B in B if movie_B["imdbnumber"] in symet]
  '''

  @staticmethod
  def intersect(A, B):
    """ Returns the intersection between A and B. About data return: B > A """
    A_movies = set([x["imdbnumber"] for x in A])
    B_movies = set([x["imdbnumber"] for x in B])
    inter = A_movies & B_movies
    return [movie_B for movie_B in B if movie_B["imdbnumber"] in inter], inter

  @staticmethod
  def union(A, B):
    A_movies = set([x["imdbnumber"] for x in A])
    B_movies = set([x["imdbnumber"] for x in B])
    union = A_movies | B_movies
    return [movie_B for movie_B in B if movie_B["imdbnumber"] in union], union

  @staticmethod
  def get_movies(playcount="1+"):
    movies_list = []
    movies = json.loads(xbmc.executeJSONRPC(json.dumps({
          "jsonrpc": "2.0",
          "method": "VideoLibrary.GetMovies",
          "params": {
            "limits": {
              "start": 0,
              "end": 0
            },
            "properties": [
              "playcount",
              "imdbnumber",
              "file",
              "lastplayed",
              "year"
            ],
            "sort": {
              "order": "ascending",
              "method": "playcount",
              #"ignorearticle": True
            }
          },
          "id": "libMovies"
      })))["result"]["movies"]
    for movie in movies:
      if str(movie["playcount"]) in playcount or (movie["playcount"]>playcount and "+" in playcount):
        movies_list.append(movie)
    return movies_list

  @staticmethod
  def get_episodes():
    shows_library = json.loads(xbmc.executeJSONRPC(json.dumps({
      "jsonrpc": "2.0",
      "method": "VideoLibrary.GetTVShows",
      "params": {
        "limits": {"start": 0, "end": 0},
        "properties": ["imdbnumber", "title", "watchedepisodes", "year"],
        "sort": {"order": "ascending", "method": "season"}
      },
      "id": "libMovies"
    })))
    if shows_library["result"]["limits"]["total"] == 0: return None
    list_tvshows = []
    for tvshow in shows_library["result"]["tvshows"]:
      list_episodes = []
      episodes = json.loads(xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0",
        "method": "VideoLibrary.GetEpisodes",
        "params": {
          "limits": {"start": 0, "end": 0},
          "properties": ["playcount", "season", "episode", "lastplayed", "tvshowid"],
          "sort": {"order": "ascending", "method": "playcount"},
          #"season": season["season"],
          "tvshowid": tvshow["tvshowid"]
        },
        "id": tvshow["tvshowid"]
      })))

      if episodes["result"]["limits"]["end"] > 0:
        for episode in episodes["result"]["episodes"]:
          if episode["playcount"] > 0: list_episodes.append(episode)
      if len(list_episodes) > 0:
        list_tvshows.append({
          "title":tvshow["title"],
          "year":tvshow["year"],
          "imdbnumber":tvshow["imdbnumber"],
          "episodes":list_episodes})

    return list_tvshows

  @staticmethod
  def update_movie(movie):
    movie1 = {"movieid":movie["movieid"], "playcount":movie["playcount"]} #Y tho?
    r = xbmc.executeJSONRPC(json.dumps({
      "jsonrpc": "2.0",
      "method": "VideoLibrary.SetMovieDetails",
      "params": movie1
      }))
    xbmc.log(str(r))

class Player(xbmc.Player):
  """ Replaces the Kodi player class """
  def __init__(self):
    xbmc.Player.__init__(self)

  @staticmethod
  def getMediaType():
    """ Returns the MediaType of the file currently playing """
    if xbmc.getCondVisibility('Container.Content(tvshows)'):
      return "show"
    elif xbmc.getCondVisibility('Container.Content(seasons)'):
      return "season"
    elif xbmc.getCondVisibility('Container.Content(episodes)'):
      return "episode"
    elif xbmc.getCondVisibility('Container.Content(movies)'):
      return "movie"
    else:
      return None

  def onPlayBackStarted(self):
    """ Activated at start """
    #self.onPlayBackStopped()
    pass
  def onPlayBackSeek(self, *args):
    """ Activated on seek """
    self.onPlayBackStopped()
  def onPlayBackResumed(self):
    """ Activated on resume """
    self.onPlayBackStopped()
  def onPlayBackEnded(self):
    """ Activated at end """
    xbmc.log("Simkl: ONPLAYBACKENDED")
    self.onPlayBackStopped()

  def onPlayBackStopped(self):
    ''' Gets the info needed to pass to the api '''
    self.api.check_connection()
    try:
      item = json.loads(xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0", "method": "Player.GetItem",
        "params": {
          "properties": ["showtitle", "title", "season", "episode", "file", "tvshowid", "imdbnumber", "year" ],
          "playerid": 1},
        "id": "VideoGetItem"})))["result"]["item"]
      if item["tvshowid"] != -1:
        item["imdbnumber"] = json.loads(xbmc.executeJSONRPC(json.dumps({
          "jsonrpc": "2.0", "method":"VideoLibrary.GetTVShowDetails",
          "params":{"tvshowid":item["tvshowid"], "properties":["imdbnumber"]},
          "id":1
          })))["result"]["tvshowdetails"]["imdbnumber"]
      xbmc.log("Simkl: Full: {0}".format(item))

      percentage = min(99, 100 * self.getTime() / self.getTotalTime())
      pctconfig  = int(self.addon.getSetting("scr-pct"))

      if percentage > pctconfig:
        bubble = __addon__.getSetting("bubble")
        r = self.api.watched(item, self.getTotalTime())

        if bubble=="true" and r:
          if item["label"] == os.path.basename(item["file"]):
          #if True: #For testing purposes
            xbmc.log("Simkl: Label and file are the same")
            lstw = self.api.lastwatched
            if lstw["type"] == "episode":
              item["showtitle"] = lstw["show"]["title"]
              item["season"] = lstw["episode"]["season"]
              item["episode"] = lstw["episode"]["episode"]
            elif lstw["type"] == "movie":
              item["title"] = "".join([lstw["movie"]["title"], " (", str(lstw["movie"]["year"]), ")"])

          txt = item["label"]
          title = ""
          if item["type"] == "movie":
            txt = "".join([item["title"], " (", str(item["year"]), ")"])
          elif item["type"] == "episode":
            txt = item["showtitle"]
            title = "- S{:02}E{:02}".format(item["season"], item["episode"])
          xbmc.log("Simkl: " + "; ".join([item["type"], txt, title]))
          interface.notify(getstr(32028).format(title), title=txt)
          r = 0

    except RuntimeError:
      pass
    except ZeroDivisionError:
      self.onPlayBackStopped()
