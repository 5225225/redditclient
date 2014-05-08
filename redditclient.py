import time
import sys
import os
import textwrap
import subprocess
import re
import warnings

import praw
import requests

import curses
import curses.ascii

tags = {}


def cursesinit():
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    curses.start_color()
    

def cursesexit():
    curses.nocbreak()
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


def filtercomment(comment):
    """
    Given a Comment object, if this function returns False the comment will
    not be displayed, along with any subcomments
    """

    if comment.ups < comment.downs:
        return False
    return True


def printsubmission(sub, index, stdscr):
    stdscr.addstr(str(index), curses.A_BOLD)
    stdscr.addstr(": ")
    title = sub.title
    if len(str(index)) + 2 + len(sub.title) > width:
        title = title[:width - (len(str(index)) + 3)]
    stdscr.addstr(title)
    stdscr.addstr("\n")

    stdscr.addstr("(")
    stdscr.addstr(str(sub.ups), colours.red)

    stdscr.addstr("|")
    stdscr.addstr(str(sub.downs), colours.blue)
    stdscr.addstr(")")
    stdscr.addstr(" submitted by ")
    stdscr.addstr(str(sub.author))
    if subreddit.display_name == "all":
        stdscr.addstr(" to ")
        stdscr.addstr(sub.subreddit.display_name, curses.A_UNDERLINE)
    stdscr.addstr(" " + sub.domain, colours.yellow)
    stdscr.addstr("\n\n")


def updatestatusbar(screen):
    screen.addstr(0,0,"asdf asdf adsf")


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


def viewcomments(sub, scr):
    sub.replace_more_comments(limit=4, threshold=0)
    comments = parsecomments(sub.comments)

    scr.clear()

    scr.addstr(sub.title + "\n")

    if sub.is_self and sub.selftext != "":
        scr.addstr(termdown(sub.selftext)+"\n")
        scr.addstr("\n")

    scr.clear()
    for index, item in enumerate(comments):
        indent = " "*(4 * item[0])
        commenttext = textwrap.fill(item[1].body, width=width, initial_indent=indent, subsequent_indent=indent)
        scr.addstr(indent + str(item[1].author), colours.yellow)
        scr.addstr("\n")
        scr.addstr(commenttext)
        scr.addstr("\n\n")
    commandline.clear()


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
    return body

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

def refreshsubs(sorting, timeframe, limit):
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
    return subs

def readline(screen, prompt):
    output = ""
    screen.addstr(prompt)
    while True:
        char = screen.getch()
        if char == ord("\n"):
            break
        elif char == curses.ascii.ESC:
            return ""
        elif char == curses.ascii.DEL:
            curry, currx = screen.getyx()
            if currx == 1:
                return ""
                # Trying to backspace the :
                # Just exit command mode, it's what vim does.
            screen.addstr(curry, currx-1, " ")
            screen.move(curry, currx-1)
            output = output[:-1]
        else:
            output += (chr(char))
            screen.addch(char)
    return "".join(output)
    curses.noecho()


if sys.version[0] != "3":
    sys.stderr.write("You don't seem to be using python version 3\n")
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

cursesinit()

class colours:
    red = curses.color_pair(1)
    green = curses.color_pair(2)
    yellow = curses.color_pair(3)
    blue = curses.color_pair(4)

for x in range(0,255):
    curses.init_pair(x+1, x+1, 0)

# Once I get to this point, I can assume that the user is logged in.
# This client can't be used without a reddit account

subreddit = reddit.get_subreddit("python")
sorting = "hot"
timeframe = ""
subheight = 3

searchterm = ""

width = curses.COLS
height = curses.LINES 

statusscreen = curses.newwin(1, curses.COLS, 0, 0)
commandline = curses.newwin(1, curses.COLS, curses.LINES-1, 0)
line = 0
limit = 100
refreshneeded = True
mode = "normal"
viewing = "subs"
while True:
    posts = {}
    usableheight = height - 2
    # One for the top status bar, and one for the command line at the bottom.
    if refreshneeded:
        commandline.clear()
        commandline.addstr("-- loading /r/{} --".format(str(subreddit)), curses.A_BOLD)
        line = 0
        commandline.refresh()
        content = curses.newpad(5000, width)
        subs = refreshsubs(sorting, timeframe, limit)
        for index, sub in enumerate(subs):
            printsubmission(sub, index, content)
            posts[index] = sub
        refreshneeded = False
        commandline.clear()
    updatestatusbar(statusscreen)
    statusscreen.refresh()
    content.refresh(line, 0, 1,0, height-2, width)
    commandline.refresh()
    #Time to add VIM modes!
    # My goal is to allow for things like <count>operator, 5j for example.
    # I'll do that after I get the basics down, though.
    try:
        mode = "normal"
        inputlist = []
        while True:
            if mode == "normal":
                char = commandline.getch()
                commandline.refresh()
                if char == ord("j"):
                    if line + (height ) >= limit * 3:
                        pass
                    else:
                        line += 3
                    break
                elif char == ord("k"):
                    if line == 0:
                        pass
                    else:
                        line -= 3
                    break
                elif char == ord("c"):
                    subindex = readline(commandline,"index:")
                    submission = posts[int(subindex)]
                    viewcomments(submission, content)
                    content.refresh(line, 0, 1,0, height-2, width)
                elif char == ord(":"):
                    mode = "command"
                elif char == ord("r"):
                    subredditname = readline(commandline, "r/")
                    subreddit = reddit.get_subreddit(subredditname)
                    refreshneeded = True
                    break
                else:
                    pass
            if mode == "command":
                inputstr = readline(commandline, ":").strip()
                if inputstr == "q":
                    cursesexit()
                elif inputstr == "refresh":
                    subs = refreshsubs(sorting, timeframe, limit)
                elif inputstr == "showcolours":
                    content.clear()
                    for colour in range(0,256):
                        curses.init_pair(colour+1, colour, 0)
                        content.addstr("Colour: {}\n".format(colour) ,curses.color_pair(colour+1))
                commandline.erase()
                mode = "normal"
    except KeyboardInterrupt:
        cursesexit()
