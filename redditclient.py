import time
import sys
import os
import textwrap
import subprocess
import re
import warnings

import praw
import requests

class escape:
    reset = 0
    bold = 1
    underline = 4
    blink = 5


class colour:
    black = 30
    red = 31
    green = 32
    yellow = 33
    blue = 34
    cyan = 36

    bg_red = 41
    bg_green = 42
    bg_yellow = 43
    bg_blue = 45
    bg_cyan = 46
    bg_white = 47

tags = {}


def cursesinit():
    screen = curses.initscr()
    curses.noecho()
    curses.cbreak()
    screen.keypad(False)
    curses.start_color()

def cursesexit():
    curses.nocbreak()
    screen.keypad(False)
    curses.echo()
    curses.endwin()
    quit()

def uniq(inputlist):
    seen = set()
    seen_add = seen.add
    return [x for x in inputlist if x not in seen and not seen_add(x)]
    # top answer on https://stackoverflow.com/questions/480214/

def callprogram(program):
    subprocess.call(program, shell=True)


def extracturls(url):
    """
    Extract i.imgur.com urls from an imgur gallery
    """

    r = requests.get(url)
    data = r.text
    regex = re.compile("i\.imgur\.com.*\.jpg")
    matches = regex.findall(data)
    # Conversion to a set then a list is to remove duplicates
    matches = uniq(matches)
    matches = ["http://" + match for match in matches]
    matches = matches[:len(matches)//2]
    # Imgur returns thumbnails, which we don't want.
    return matches


def ansilen(text):
    """
    Return the length of a string, taking into account ANSI escape codes
    """
    length = 0
    ignore = False
    for letter in text:
        if letter == "\x1b":
            ignore = True
        if not ignore:
            length = length + 1
        if ignore and letter == "m":
            ignore = False
    return length


def ansi(code, text):
    """
    Return an ANSI SGR code, using the code and the text.
    """
    return "\x1b[{}m{}\x1b[m".format(code, text)


def filtercomment(comment):
    """
    Given a Comment object, if this function returns False the comment will
    not be displayed, along with any subcomments
    """

    if comment.ups < comment.downs:
        return False
    return True


def printsubmission(sub, index, stdscr):
    stdscr.addstr(str(index), curses.A_UNDERLINE)
    stdscr.addstr(": ")
    title = sub.title
    if len(str(index)) + 2 + len(sub.title) > width:
        title = title[:width - (len(str(index)) + 3)]
    stdscr.addstr(title)
    stdscr.addstr("\n")

    stdscr.addstr("(")
    stdscr.addstr(str(sub.ups), curses.COLOR_RED)
    stdscr.addstr("|")
    stdscr.addstr(str(sub.downs), curses.COLOR_BLUE)
    stdscr.addstr(")")
    stdscr.addstr(" submitted by ")
    stdscr.addstr(str(sub.author))
    if subreddit.display_name == "all":
        stdscr.addstr(" to ")
        stdscr.addstr(sub.subreddit.display_name, curses.A_UNDERLINE)
    stdscr.addstr(" " + sub.domain, curses.COLOR_YELLOW)
    stdscr.addstr("\n")


def updatestatusbar(screen):
    screen.addstr(0, 0, "I would put something here")

def parsecomments(comments, indentlevel=0):
    out = []
    # In the format of [indentlevel, fulltext]
    for comment in comments:
        if filtercomment(comment):
            out.append([indentlevel, comment])
            if len(comment.replies) > 0:
                for item in parsecomments(comment.replies, indentlevel+1):
                    out.append(item)

    return out


def formatcomment(subauthor, comment, index, indent):
    index = ansi(escape.bold, index)

    if subauthor == str(comment.author):
        author = ansi(colour.cyan, ansi(escape.bold, comment.author))
    else:
        author = comment.author

    upvotes = ansi(colour.red, comment.ups)
    downvotes = ansi(colour.blue, comment.downs)
    body = str("\n  ").join(textwrap.wrap(
        comment.body,
        width - (len(indent) + 2)))

    full = "{}: {} ({}|{})\n  {}\n".format(
        index,
        author,
        upvotes,
        downvotes,
        body,
        )

    return full


def viewcomments(sub):
    sub.replace_more_comments(limit=4, threshold=0)
    screen.addstr("Parsing comments...")
    comments = parsecomments(sub.comments)
    outfile = open("comments", "w")

    screen.addstr("Preparing to write comments...")
    towrite = [sub.title, ""]

    if sub.is_self and sub.selftext != "":
        towrite.append(termdown(sub.selftext))
        towrite.append("")

    x = str(sub.author)

    for index, item in enumerate(comments):
        indent = " "*(4 * item[0])
        screen.addstr("Formatting comment {} out of {}".format(index+1, len(comments)))
        for line in formatcomment(x, item[1], index, indent).split("\n"):
            towrite.append(indent + termdown(line))

    screen.addstr("Writing comments...")
    outfile.write("\n".join(towrite))
    outfile.close()

    screen.addstr("Opening comments...")
    callprogram("less -R comments")


def gettags(x, tag):
    """
    Return a list of all pairs of the tag string in x.

    The output is in the format of [[start, end],..]
    The start/end is the entire string, including the tags.
    """
    tags = []
    loc = 0
    while True:
        start = x.find(tag, loc)
        if start == -1:
            break

        end = x.find(tag, start+1)
        if end == -1:
            break

        loc = end + 1
        tags.append((start, end+len(tag)))
    return tags


def termdown(body):
    # Uses the ansi() function to convert from reddit's markdown to
    # a format that can bre read in the terminal
    # gettags does not handle something like this
    # gettags(**hello** *world*, *) properly, do the longest ones first.

    bodytext = []
    for line in body.split("\n"):
        x = line
        if x.startswith("* "):
            x = u"\u2022 " + x[2:]

        if x.startswith("    "):
            x = ansi(colour.cyan, x)

        if "**" in x:
            toreplace = []
            for start, end in gettags(x, "*"):
                toreplace.append(x[start:end])

            for item in toreplace:
                x = x.replace(item, ansi(escape.underline, item[2:-2]))

        if "*" in x:
            toreplace = []
            for start, end in gettags(x, "*"):
                toreplace.append(x[start:end])

            for item in toreplace:
                x = x.replace(item, ansi(escape.underline, item[1:-1]))
        # The previous usage was wrong, as bold/italics can't be multiline
        # However, code blocks using backtick are, so they are seperate.
        bodytext.append(x)
    body = "\n".join(bodytext)

    if "`" in body:
        toreplace = []
        for start, end in gettags(body, "`"):
            toreplace.append(body[start:end])
        for item in toreplace:
            x = x.replace(item, ansi(colour.cyan, item[1:-1]))

    body = body.replace("&gt;", ">")
    return body



if sys.version[0] != "3":
    screen.addstr("You don't seem to be using python version 3")
    sys.exit(0)

reddit = praw.Reddit(user_agent="command line reddit client by /u/5225225")

if len(sys.argv) == 1:
    username = input("Enter username: ")
    password = promptpassword("Enter password: ")
elif len(sys.argv) == 2:
    username = sys.argv[1]
    password = promptpassword("Enter password: ")
else:
    username = sys.argv[1]
    password = sys.argv[2]

if username == "" or password == "":
    screen.addstr("Invalid username or password")
    sys.exit(1)

try:
    with warnings.catch_warnings():
        reddit.login(username, password)
except praw.errors.InvalidUserPass:
    screen.addstr("Invalid username or password")
    sys.exit(1)

import curses
screen = curses.initscr()
curses.start_color()
curses.noecho()
curses.cbreak()
screen.keypad(False)

# Once I get to this point, I can assume that the user is logged in.
# This client can't be used without a reddit account

subreddit = reddit.get_subreddit("python")
sorting = "hot"
timeframe = ""
subheight = 3

viewmode = "normal"
searchterm = ""

statusscreen = curses.newwin(1, curses.COLS, 0, 0)
commandline = curses.newwin(1, curses.COLS, curses.LINES-1, 0)
while True:
    width = curses.COLS
    height = curses.LINES 
    posts = {}
    usableheight = height - 2
    # One for the top status bar, and one for the command line at the bottom.
    limit = 20

    listingpad = curses.newpad(limit*3, width)

    if viewmode == "normal":
        if sorting == "hot":
            subs = subreddit.get_hot(limit=limit)

        elif sorting == "controversial":
            if timeframe == "":
                subs = subreddit.get_controversial(limit=limit)
            elif timeframe == "hour":
                subs = subreddit.get_controversial_from_hour(limit=limit)
            elif timeframe == "day":
                subs = subreddit.get_controversial_from_day(limit=limit)
            elif timeframe == "week":
                subs = subreddit.get_controversial_from_week(limit=limit)
            elif timeframe == "month":
                subs = subreddit.get_controversial_from_month(limit=limit)
            elif timeframe == "year":
                subs = subreddit.get_controversial_from_year(limit=limit)
            elif timeframe == "all":
                subs = subreddit.get_controversial_from_all(limit=limit)
        elif sorting == "new":
            subs = subreddit.get_new(limit=limit)

        elif sorting == "rising":
            subs = subreddit.get_rising(limit=limit)

        elif sorting == "top":
            if timeframe == "":
                subs = subreddit.get_top(limit=limit)
            elif timeframe == "hour":
                subs = subreddit.get_top_from_hour(limit=limit)
            elif timeframe == "day":
                subs = subreddit.get_top_from_day(limit=limit)
            elif timeframe == "week":
                subs = subreddit.get_top_from_week(limit=limit)
            elif timeframe == "month":
                subs = subreddit.get_top_from_month(limit=limit)
            elif timeframe == "year":
                subs = subreddit.get_top_from_year(limit=limit)
            elif timeframe == "all":
                subs = subreddit.get_top_from_all(limit=limit)
    for index, sub in enumerate(subs):
        if index >= limit:
            break
        printsubmission(sub, index, listingpad)
        posts[index] = sub
    line = 0
    screen.move(height-1, 0)
    updatestatusbar(statusscreen)
    statusscreen.refresh()
    listingpad.refresh(line, 0, 1,0, height-2, width)
    commandline.addstr(0, 0, ":")
    commandline.refresh()
    try:
        mode = "normal"
        while True:
            char = commandline.getch()
            if mode == "normal":
                if char == ord("j"):
                    line += 3
                    break
                elif char == ord("k"):
                    line -= 3
                    break
                else:
                    commandline.addchr(chr(char))
    except KeyboardInterrupt:
        cursesexit()
#   elif command == "p":
#       subfile = open("/tmp/selfpost", "w")
#       contents = """<Replace this line with the post title>

#rite your post here"""
#       subfile.write(contents)
#       subfile.close()
#       callprogram("vim /tmp/selfpost")
#       body = open("/tmp/selfpost").read().split("\n")
#       title = body[0].strip()
#       content = "\n".join(body[2:])
#       reddit.submit(subreddit, title, content)
#   elif command.startswith("r"):
#       subreddit = reddit.get_subreddit(command[1:], fetch=True)
#       

#   elif command.startswith("o"):
#       post = posts[int(command[2:])]
#       if command[1] == "c":
#           screen.addstr("Loading comments...\n")
#           sub = posts[int(command[2:])]
#           viewcomments(sub)
#       elif command[1] == "i":
#           callprogram("feh -F {}".format(post.url))
#       elif command[1] == "l":
#           if "i.imgur.com" in post.url:
#               callprogram("feh -F {}".format(post.url))
#           if "imgur.com" in post.url:
#               urls = extracturls(post.url)
#               callprogram("feh -F {}".format(" ".join(urls)))
#           elif "youtube.com" in post.url:
#               callprogram("vlc -f {}".format(post.url))
#           else:
#               callprogram("w3m {}".format(post.url))
#   elif command == "desc":
#       outfile = open("sidebar", "w")
#       sidebar = termdown(subreddit.description)
#       outfile.write(sidebar)
#       outfile.close()
#       callprogram("less -R sidebar")
#   elif command.startswith("/"):
#       searchterm = command[1:]
#       viewmode = "search"
#   elif command == "pdbstart":
#       import pdb
#       pdb.set_trace()
#   elif command in ["q", "quit"]:
#       sys.exit(0)
